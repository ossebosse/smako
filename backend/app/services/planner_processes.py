"""Split planner work over the machine's cores (owner goal 2026-11-17).

Smako's planner is Python and runs on one core at a time. The work that
dominates a first plan in a large area – pricing every candidate recipe on
its own in every selected store – is independent per recipe. This module runs
such work in forked worker processes: each child starts as an exact copy of
the planner (prepared universe, product facts, warm caches) without loading
or copying anything, does its slice, and sends back only small, picklable
results. The parent keeps every decision: it merges the results into the same
rows a serial run would produce and continues exactly as before.

Safety:
- Linux only (``os.fork``); anything else, a failed fork, a crashed or late
  child, or an unreadable answer means the parent does that slice itself.
- Children never write files, logs or shared caches; they exit with
  ``os._exit`` so no atexit handler, flush or finaliser of the parent runs.
- A child that waits on a lock another thread held at fork time is killed at
  the slice deadline; the parent then does the work itself.

``SMAKO_PLANNER_PROCESSES``: worker processes per request. Default: every core
but one, at most 8; ``0`` or ``1`` turns it off.
"""
from __future__ import annotations

import os
import pickle
import select
import signal
import sys
import time
import warnings
from collections.abc import Callable, Sequence

_MIN_ITEMS_PER_WORKER = 24


def worker_count() -> int:
    if not hasattr(os, "fork") or sys.platform != "linux":
        return 0
    raw = os.environ.get("SMAKO_PLANNER_PROCESSES")
    if raw is not None:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    return max(0, min(8, (os.cpu_count() or 1) - 1))


def run_in_processes(items: Sequence, work: Callable[[Sequence], dict], *, timeout: float,
                     workers: int | None = None) -> tuple[dict, list[int]]:
    """Run ``work`` over slices of ``items`` in forked children.

    Returns the merged answers and the indexes of the slices that produced
    nothing (to be done by the caller). ``work`` must return a picklable dict.
    """
    workers = worker_count() if workers is None else workers
    slices = _slices(len(items), workers)
    if len(slices) < 2:
        return {}, list(range(len(slices)))
    children = {}
    missing = []
    for index, (start, stop) in enumerate(slices):
        read, write = os.pipe()
        try:
            with warnings.catch_warnings():
                # 3.12 warns about fork in a threaded process; see module notes.
                warnings.simplefilter("ignore", DeprecationWarning)
                pid = os.fork()
        except OSError:
            os.close(read)
            os.close(write)
            missing.append(index)
            continue
        if pid == 0:  # child
            status = 1
            try:
                os.close(read)
                answer = pickle.dumps(work(items[start:stop]), protocol=pickle.HIGHEST_PROTOCOL)
                with os.fdopen(write, "wb") as out:
                    out.write(answer)
                status = 0
            except BaseException:  # noqa: BLE001, S110 - the parent redoes this slice
                status = 1
            finally:
                os._exit(status)
        os.close(write)
        children[read] = (pid, index, bytearray())
    deadline = time.monotonic() + max(0.0, timeout)
    answers: dict = {}
    while children:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        ready, _, _ = select.select(list(children), [], [], left)
        for fd in ready:
            pid, index, buffer = children[fd]
            chunk = os.read(fd, 1 << 20)
            if chunk:
                buffer.extend(chunk)
                continue
            os.close(fd)
            del children[fd]
            _, status = os.waitpid(pid, 0)
            if status == 0:
                try:
                    answers.update(pickle.loads(bytes(buffer)))
                    continue
                except Exception:  # noqa: BLE001 - an unreadable answer is redone here
                    status = 1
            missing.append(index)
    for fd, (pid, index, _) in children.items():  # late: stop and redo here
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except OSError:
            pass
        os.close(fd)
        missing.append(index)
    return answers, sorted(missing)


def slices_of(items: Sequence, workers: int) -> list[Sequence]:
    return [items[a:b] for a, b in _slices(len(items), workers)]


def _slices(count: int, workers: int) -> list[tuple[int, int]]:
    parts = min(workers, count // _MIN_ITEMS_PER_WORKER)
    if parts < 2:
        return [(0, count)] if count else []
    size, extra = divmod(count, parts)
    bounds, start = [], 0
    for part in range(parts):
        stop = start + size + (part < extra)
        bounds.append((start, stop))
        start = stop
    return bounds
