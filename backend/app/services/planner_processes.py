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
but one, at most 8; ``0`` or ``1`` turns it off. Plans running at the same
time share them: each gets its part of the cores.

Several people at once (``run_plan_in_process``): each plan runs in its own
forked process, so plans no longer take turns on one core. The child reports
its stages through a pipe and sends back the plan (or its error) together with
what it learned for later plans: the qualification rows and package quotes it
computed (``register_warm_cache``). The parent stops a child when the request
is cancelled, and plans in its own thread if a child dies.
``SMAKO_PLAN_PROCESSES=0`` turns this off.
"""
from __future__ import annotations

import itertools
import logging
import os
import pickle
import select
import signal
import struct
import sys
import threading
import time
import warnings
import weakref
from collections.abc import Callable, Sequence

_MIN_ITEMS_PER_WORKER = 24
logger = logging.getLogger(__name__)

# Plans running in their own process right now (parent) / at this child's
# start (child): the cores are shared between them.
_running_plans = 0
_running_lock = threading.Lock()
_plan_share = 1


def _fork_supported() -> bool:
    return hasattr(os, "fork") and sys.platform == "linux"


def worker_count() -> int:
    if not _fork_supported():
        return 0
    raw = os.environ.get("SMAKO_PLANNER_PROCESSES")
    if raw is not None:
        try:
            wanted = max(0, int(raw))
        except ValueError:
            return 0
    else:
        wanted = max(0, min(8, (os.cpu_count() or 1) - 1))
    return wanted // max(1, _plan_share)


def plan_processes_enabled() -> bool:
    return _fork_supported() and os.environ.get("SMAKO_PLAN_PROCESSES", "1") not in {"0", "false", ""}


# Caches whose new entries a plan process sends back, and whose locks a child
# must not inherit held by a thread that does not exist in the child.
_ids = itertools.count()
_warm_caches: dict[int, weakref.ref] = {}
_fork_safe = weakref.WeakSet()


def register_warm_cache(cache) -> None:
    """``cache`` has start_journal(), journal() and absorb(entries)."""
    key = next(_ids)
    _warm_caches[key] = weakref.ref(cache, lambda _ref, key=key: _warm_caches.pop(key, None))


def register_fork_safe(obj) -> None:
    """``obj._after_fork()`` replaces its locks in a newly forked child."""
    _fork_safe.add(obj)


def _reinit_after_fork() -> None:
    for obj in list(_fork_safe):
        try:
            obj._after_fork()
        except Exception:  # noqa: BLE001, S110 - a child that then hangs is stopped by its parent
            pass


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reinit_after_fork)


def run_in_processes(items: Sequence, work: Callable[[Sequence], object], *, timeout: float,
                     workers: int | None = None) -> tuple[list, list[int]]:
    """Run ``work`` over slices of ``items`` in forked children.

    Returns the answers of the slices that finished (in slice order) and the
    indexes of the slices that produced nothing (to be done by the caller).
    ``work`` must return something picklable.
    """
    workers = worker_count() if workers is None else workers
    slices = _slices(len(items), workers)
    if len(slices) < 2:
        return [], list(range(len(slices)))
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
            except BaseException:  # noqa: BLE001 - the parent redoes this slice
                status = 1
            finally:
                os._exit(status)
        os.close(write)
        children[read] = (pid, index, bytearray())
    deadline = time.monotonic() + max(0.0, timeout)
    answers: dict[int, object] = {}
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
                    answers[index] = pickle.loads(bytes(buffer))
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
    return [answers[i] for i in sorted(answers)], sorted(missing)


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


def _send(fd: int, message) -> None:
    data = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
    view = memoryview(struct.pack("!Q", len(data)) + data)
    while view:
        view = view[os.write(fd, view):]


def _frames(buffer: bytearray):
    while len(buffer) >= 8:
        (size,) = struct.unpack("!Q", buffer[:8])
        if len(buffer) < 8 + size:
            return
        data = bytes(buffer[8:8 + size])
        del buffer[:8 + size]
        yield pickle.loads(data)


def _warm_journals():
    caches = {key: ref() for key, ref in list(_warm_caches.items())}
    return {key: cache for key, cache in caches.items() if cache is not None}


def start_warm_journals():
    """In a child: record what the registered caches compute from now on."""
    if os.environ.get("SMAKO_PLANNER_RETURN_CACHES", "1") == "0":
        return {}
    caches = _warm_journals()
    for cache in caches.values():
        cache.start_journal()
    return caches


def warm_journals(caches) -> dict:
    return {key: cache.journal() for key, cache in caches.items()}


def absorb_warm(warm) -> int:
    """In the parent: keep what a child computed (registered caches only)."""
    caches, added = _warm_journals(), 0
    for key, entries in (warm or {}).items():
        cache = caches.get(key)
        if cache is not None and entries:
            try:
                added += cache.absorb(entries) or 0
            except Exception:
                logger.warning("plan_process could not keep warm entries", exc_info=True)
    return added


def run_plan_in_process(work: Callable[[], object]):
    """Run one whole plan (``work``) in its own process; see the module notes.

    Called from the request's worker thread, whose context (deadline, stage
    reporters, cancellation) the child inherits. Returns ``work()``'s value or
    raises its error, as running it here would.
    """
    from app.services import plan_jobs

    if not plan_processes_enabled():
        return work()
    global _running_plans
    read, write = os.pipe()
    with _running_lock:
        _running_plans += 1
        share = _running_plans
    try:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                pid = os.fork()
        except OSError:
            os.close(read)
            os.close(write)
            return work()
        if pid == 0:  # child
            _run_plan_child(work, read, write, share)
        os.close(write)
        return _await_plan_child(work, pid, read, plan_jobs)
    finally:
        with _running_lock:
            _running_plans -= 1


def _run_plan_child(work, read, write, share):  # pragma: no cover - runs in the child
    global _plan_share
    status = 1
    try:
        os.close(read)
        _plan_share = share
        from app.services import plan_jobs
        plan_jobs._stage_reporter.set(lambda stage, progress: _send(write, ("stage", stage, progress)))
        plan_jobs._engine_reporter.set(lambda limit: _send(write, ("engine", limit)))
        caches = start_warm_journals()
        try:
            outcome = ("result", work())
        except BaseException as error:  # noqa: BLE001 - sent to the parent, raised there
            outcome = ("error", error)
        warm = warm_journals(caches)
        try:
            _send(write, (*outcome, warm))
        except Exception:  # noqa: BLE001 - e.g. an error that cannot be pickled
            _send(write, ("lost", None, warm))
        status = 0
    except BaseException:  # noqa: BLE001, S110 - the parent plans itself
        pass
    finally:
        os._exit(status)


def _await_plan_child(work, pid, read, plan_jobs):
    buffer, final = bytearray(), None
    stop = plan_jobs._work_cancellation.get()
    stage_reporter, engine_reporter = plan_jobs._stage_reporter.get(), plan_jobs._engine_reporter.get()
    try:
        while True:
            if stop is not None and stop.is_set():
                _stop(pid)
                pid = None
                plan_jobs.check_cancelled()  # raises the cancellation
            ready, _, _ = select.select([read], [], [], 0.25)
            if not ready:
                continue
            chunk = os.read(read, 1 << 20)
            if not chunk:
                break
            buffer.extend(chunk)
            for message in _frames(buffer):
                if message[0] == "stage" and stage_reporter:
                    stage_reporter(message[1], message[2])
                elif message[0] == "engine" and engine_reporter:
                    engine_reporter(message[1])
                elif message[0] in {"result", "error", "lost"}:
                    final = message
    finally:
        os.close(read)
        if pid is not None:
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass
    if final is None or final[0] == "lost":
        logger.warning("plan_process lost=%s; planning in the request thread", "answer" if final else "child")
        if final is not None:
            absorb_warm(final[2])
        return work()
    absorb_warm(final[2])
    if final[0] == "error":
        raise final[1]
    return final[1]


def _stop(pid) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except OSError:
        pass
