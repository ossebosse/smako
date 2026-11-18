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

Budget (``reserve_processes``): every extra process, a plan's own or a
qualification worker, takes one slot from a single allocator in the app
process. A slot needs a free core (``SMAKO_PLANNER_PROCESSES``, default every
core but one, at most 8) AND room in memory now: CPython writes a reference
count into every object a process reads, so a child copies whatever it
touches. The allocator expects the largest child of the same kind seen so
far (``observe_child``): a plan's own process copies up to 2.7 GB, a
qualification worker 0.2–0.45 GB (Malmö, 2026-11-18). What a running plan
has copied is already gone from the free memory; only what it may still
copy is held back. Three plans with their own
workers ran a 7 GB container out of memory before the allocator existed. Plans running at the same time share the cores.
Children are marked as the first processes to stop if memory still runs out,
so the web app itself is never the one stopped.

Several people at once (``run_plan_in_process``): each plan runs in its own
forked process when a slot is free, so plans no longer take turns on one
core. A plan's own process takes one slot; when its qualification starts it
asks the app process over a pipe for workers, granted with the plans and the
memory of that moment. The child reports its stages through a pipe and sends back the plan (or
its error) together with what it learned for later plans: the qualification
rows, package quotes and product resolutions it computed
(``register_warm_cache``). The parent stops a child when the request is
cancelled, and plans in its own thread if a child dies or no slot is free.
``SMAKO_PLAN_PROCESSES=0`` turns this off.
"""
from __future__ import annotations

import contextvars
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
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager

_MIN_ITEMS_PER_WORKER = 24
_MEMORY_HEADROOM = 0.75  # share of the memory available now that children may use
logger = logging.getLogger(__name__)

# Allocator state, in the app process: plans running now and slots in use.
_running_plans = 0
_slots_in_use = 0
# Memory promised to running children: workers by their estimate; a plan's
# own process by what it may still copy (estimate minus what it has).
_worker_slots = 0
_worker_bytes = 0
_plan_children: dict[object, list[int]] = {}
_running_lock = threading.Lock()
# In a plan's own process: the pipes to ask the app process for workers.
_parent_channel: tuple[int, int] | None = None


def _child_after_fork() -> None:
    import gc
    global _running_lock, _running_plans, _slots_in_use, _parent_channel, _worker_slots, _worker_bytes
    _running_lock = threading.Lock()  # another thread may have held it at the fork
    _running_plans = _slots_in_use = _worker_slots = _worker_bytes = 0
    _plan_children.clear()
    _parent_channel = None
    # Everything inherited stays out of this child's garbage collection: a
    # collection writes to every object it visits and so copies its memory.
    gc.freeze()
    try:  # if memory runs out after all, stop a child, never the web app
        with open("/proc/self/oom_score_adj", "w") as adj:
            adj.write("800")
    except OSError:
        pass


def _fork_supported() -> bool:
    return hasattr(os, "fork") and sys.platform == "linux"


def cpu_budget() -> int:
    """Extra processes the cores allow for the whole app."""
    if not _fork_supported():
        return 0
    raw = os.environ.get("SMAKO_PLANNER_PROCESSES")
    if raw is not None:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    return max(0, min(8, _cores() - 1))


def _cores() -> int:
    """Cores this container may use: the machine's, or fewer under a CPU quota."""
    cores = os.cpu_count() or 1
    try:
        with open("/sys/fs/cgroup/cpu.max") as limit:
            quota, period = limit.read().split()[:2]
        if quota != "max":
            cores = min(cores, max(1, -(-int(quota) // int(period))))
    except (OSError, ValueError):
        pass
    return cores


def _read_int(path: str) -> int | None:
    try:
        with open(path) as handle:
            text = handle.read().strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def _available_bytes() -> int | None:
    """Memory that may still be used now: the container's limit and the machine's."""
    values = []
    limit, current = _read_int("/sys/fs/cgroup/memory.max"), _read_int("/sys/fs/cgroup/memory.current")
    if limit is not None and current is not None:
        values.append(limit - current)
    try:
        with open("/proc/meminfo") as info:
            for line in info:
                if line.startswith("MemAvailable:"):
                    values.append(int(line.split()[1]) * 1024)
                    break
    except OSError:
        pass
    return min(values) if values else None


def _own_anon_bytes() -> int | None:
    try:
        with open("/proc/self/status") as status:
            for line in status:
                if line.startswith("RssAnon:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return None


# The most memory a child of each kind has copied so far (``observe_child``):
# a plan's own process and a qualification worker differ tenfold. Measured on
# the beta 2026-11-18: a Malmö plan's process copies up to 2.7 GB (it reads
# the whole price universe and builds its caches), a worker 0.2–0.45 GB.
# Until one is seen, half of this process's private memory, at most these.
_observed_peak = {"plan": 0, "worker": 0}
_UNSEEN_CHILD_BYTES = {"plan": 3 << 30, "worker": 1 << 30}


def _private_dirty(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/smaps_rollup") as rollup:
            for line in rollup:
                if line.startswith("Private_Dirty:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


def observe_child(pid: int, kind: str = "worker") -> int | None:
    """Note how much memory a running child has copied (its private pages)."""
    size = _private_dirty(pid)
    if size is not None:
        note_child_peak(kind, size)
    return size


def note_child_peak(kind: str, size: int) -> None:
    """A child's copied memory, measured here or reported by a plan's process."""
    if size and size > _observed_peak[kind]:
        _observed_peak[kind] = size


def _child_bytes(kind: str = "worker") -> int | None:
    """Expected memory of one more child of ``kind``: the largest seen, +25 %.

    A child copies only what it changes, not its parent's size. The earlier
    floor of half the parent's private memory grew with the warm caches, and
    one peak for every child let a plan's 2.7 GB process stand for every
    worker: on 2026-11-18 a new nutrition requirement got no worker at all
    and took 60–80 s of qualification on one core.
    """
    own = _own_anon_bytes()
    if not own:
        return None
    if _observed_peak[kind]:
        return int(_observed_peak[kind] * 1.25)
    return int(min(own / 2, _UNSEEN_CHILD_BYTES[kind]))


def _promised_bytes() -> int:
    """Memory running children may still take: not counted in what is free now."""
    with _running_lock:
        plans = sum(max(0, estimate - copied) for estimate, copied in _plan_children.values())
        return _worker_bytes + plans


def memory_slots(kind: str = "worker") -> int:
    """More children of ``kind`` that fit in memory now (unknown memory: none).

    What running plans have copied is already gone from the free memory; what
    they may still copy, and every running worker's estimate, is held back,
    so plans starting at once never each see the same free memory.
    """
    if os.environ.get("SMAKO_PLANNER_MEMORY_CHECK", "1") == "0":
        return 1 << 16
    available, child = _available_bytes(), _child_bytes(kind)
    if not available or not child:
        return 0
    return max(0, int((available * _MEMORY_HEADROOM - _promised_bytes()) // child))


def reserve_processes(wanted: int) -> int:
    """Take up to ``wanted`` worker slots; returns how many were granted (maybe 0)."""
    global _slots_in_use, _worker_slots, _worker_bytes
    if wanted <= 0:
        return 0
    memory = memory_slots("worker")
    child = _child_bytes("worker") or 0
    with _running_lock:
        granted = max(0, min(wanted, cpu_budget() - _slots_in_use, memory))
        _slots_in_use += granted
        _worker_slots += granted
        _worker_bytes += granted * child
    return granted


def release_processes(count: int) -> None:
    global _slots_in_use, _worker_slots, _worker_bytes
    if count > 0:
        with _running_lock:
            count = min(count, _worker_slots)
            if _worker_slots:
                _worker_bytes -= _worker_bytes * count // _worker_slots
            _worker_slots -= count
            _slots_in_use = max(0, _slots_in_use - count)
            if not _worker_slots:
                _worker_bytes = 0


def reserve_plan_process() -> object | None:
    """A slot for one plan's own process, or None (the plan runs here)."""
    global _slots_in_use
    memory = memory_slots("plan")
    estimate = _child_bytes("plan") or 0
    with _running_lock:
        if min(cpu_budget() - _slots_in_use, memory) < 1:
            return None
        _slots_in_use += 1
        token = object()
        _plan_children[token] = [estimate, 0]
        return token


def observe_plan_process(token: object, pid: int) -> None:
    size = observe_child(pid, "plan")
    if size is not None:
        with _running_lock:
            if token in _plan_children:
                _plan_children[token][1] = max(_plan_children[token][1], size)


def release_plan_process(token: object | None) -> None:
    global _slots_in_use
    if token is None:
        return
    with _running_lock:
        if _plan_children.pop(token, None) is not None:
            _slots_in_use = max(0, _slots_in_use - 1)


def _fair_share() -> int:
    with _running_lock:
        running = max(1, _running_plans)
    return cpu_budget() // running


def worker_count() -> int:
    """Worker processes one plan would ask for now (its share of the cores)."""
    return _fair_share()


# Background work (the warm-up after a start): runs at the lowest CPU priority
# and gets at most one worker, so people's plans always come first. After the
# 2026-11-17 activation the warm-up took every worker for ten minutes after a
# start, and the first plans of real people ran out of time beside it.
_background = contextvars.ContextVar("smako_background_work", default=False)
_BACKGROUND_WORKERS = 1
_BACKGROUND_NICE = 19


def run_in_background_thread(work: Callable[[], object], name: str = "smako-background"):
    """Run ``work`` in its own low-priority thread; returns a concurrent Future.

    The thread's priority cannot be raised again without privileges, so the
    work never runs on a shared pool thread. Its worker processes inherit the
    priority.
    """
    from concurrent.futures import Future

    future: Future = Future()

    def target():
        try:
            os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), _BACKGROUND_NICE)
        except (AttributeError, OSError):
            pass
        _background.set(True)
        try:
            future.set_result(work())
        except BaseException as error:  # noqa: BLE001 - handed to the caller
            future.set_exception(error)

    threading.Thread(target=target, name=name, daemon=True).start()
    return future


@contextmanager
def qualification_workers() -> Iterator[int]:
    """Workers this plan's qualification may fork now (slots held meanwhile).

    In a plan's own process the app process decides, with the plans and the
    memory of that moment; the plan's own process is already one of its cores.
    """
    background = _background.get()
    if free_threaded():  # threads share memory: only the cores count
        yield min(_fair_share(), _BACKGROUND_WORKERS) if background else _fair_share()
        return
    if _parent_channel is not None:
        granted = _ask_parent("reserve", 0)
        try:
            yield granted
        finally:
            # The workers' size, measured in this process, for the allocator.
            _ask_parent("release", granted, _observed_peak["worker"])
        return
    granted = reserve_processes(min(_fair_share(), _BACKGROUND_WORKERS) if background else _fair_share())
    try:
        yield granted
    finally:
        release_processes(granted)


def _ask_parent(kind: str, count: int, *extra) -> int:
    write, reply = _parent_channel
    _send(write, (kind, count, *extra))
    if kind != "reserve":
        return 0
    data = b""
    while len(data) < 4:
        chunk = os.read(reply, 4 - len(data))
        if not chunk:
            return 0
        data += chunk
    return struct.unpack("!I", data)[0]


def free_threaded() -> bool:
    """Python without the GIL: threads run at the same time and share memory."""
    return hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()


def plan_processes_enabled() -> bool:
    if free_threaded():
        return False  # plans are threads already; nothing to copy
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
                     workers: int | None = None, here: bool = False) -> tuple[list, list[int]]:
    """Run ``work`` over slices of ``items`` in forked children.

    Returns the answers of the slices that finished (in slice order) and the
    indexes of the slices that produced nothing (to be done by the caller).
    ``work`` must return something picklable. With ``here`` this process
    does the first slice itself while the children do the rest, so ``workers``
    children keep ``workers + 1`` cores busy.
    """
    workers = worker_count() if workers is None else workers
    slices = _slices(len(items), workers + (1 if here else 0))
    if len(slices) < 2:
        return [], list(range(len(slices)))
    children = {}
    missing = []
    for index, (start, stop) in enumerate(slices):
        if here and index == 0:
            continue
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
                _child_after_fork()
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
    if here:
        try:
            answers[0] = work(items[slices[0][0]:slices[0][1]])
        except Exception:  # noqa: BLE001 - redone by the caller, as a child's slice would be
            missing.append(0)
    sampled = 0.0
    while children:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        if time.monotonic() - sampled >= 1:
            sampled = time.monotonic()
            for pid, _, _ in children.values():
                observe_child(pid)
        ready, _, _ = select.select(list(children), [], [], min(left, 1.0))
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


def run_in_threads(items: Sequence, make_work: Callable[[], Callable[[Sequence], object]], *,
                   workers: int) -> tuple[list, list[int]]:
    """Free-threaded counterpart of ``run_in_processes(here=True)``.

    ``make_work()`` gives each slice its own work function (its own planner
    copy); every thread runs in a copy of this thread's context, so deadline,
    cancellation and cache sessions behave as here. Returns the answers in
    slice order and the slices that failed.
    """
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    slices = _slices(len(items), workers + 1)
    if len(slices) < 2:
        return [], list(range(len(slices)))
    tasks = [(index, make_work(), items[a:b]) for index, (a, b) in enumerate(slices)]
    answers, missing = {}, []
    with ThreadPoolExecutor(max_workers=len(slices) - 1, thread_name_prefix="smako-qualify") as pool:
        futures = {index: pool.submit(contextvars.copy_context().run, work, part)
                   for index, work, part in tasks[1:]}
        index, work, part = tasks[0]
        try:
            answers[index] = work(part)
        except Exception:  # noqa: BLE001 - redone by the caller
            missing.append(index)
        for index, future in futures.items():
            try:
                answers[index] = future.result()
            except Exception:
                logger.warning("qualification thread failed; its slice is redone", exc_info=True)
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
    raises its error, as running it here would. Without a free slot the plan
    runs here, as before.
    """
    from app.services import plan_jobs

    global _running_plans
    with _running_lock:
        _running_plans += 1
    slot = None
    try:
        if plan_processes_enabled():
            slot = reserve_plan_process()
        if slot is None:
            return work()
        read, write = os.pipe()
        reply_read, reply_write = os.pipe()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                pid = os.fork()
        except OSError:
            for fd in (read, write, reply_read, reply_write):
                os.close(fd)
            return work()
        if pid == 0:  # child
            _run_plan_child(work, read, write, reply_read, reply_write)
        os.close(write)
        os.close(reply_read)
        try:
            return _await_plan_child(work, pid, read, reply_write, plan_jobs, slot)
        finally:
            os.close(reply_write)
    finally:
        release_plan_process(slot)
        with _running_lock:
            _running_plans -= 1


def _run_plan_child(work, read, write, reply_read, reply_write):  # pragma: no cover - runs in the child
    global _parent_channel
    status = 1
    try:
        os.close(read)
        os.close(reply_write)
        _child_after_fork()
        _parent_channel = (write, reply_read)
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


def _await_plan_child(work, pid, read, reply, plan_jobs, slot=None):
    buffer, final, sampled, held = bytearray(), None, 0.0, 0
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
                if time.monotonic() - sampled >= 1:
                    sampled = time.monotonic()
                    observe_plan_process(slot, pid)
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
                elif message[0] == "reserve":
                    # The plan's own process is one core already.
                    granted = reserve_processes(max(0, _fair_share() - 1))
                    held += granted
                    try:
                        os.write(reply, struct.pack("!I", granted))
                    except OSError:
                        pass
                elif message[0] == "release":
                    if len(message) > 2:
                        note_child_peak("worker", message[2])
                    release_processes(min(held, message[1]))
                    held -= min(held, message[1])
                elif message[0] in {"result", "error", "lost"}:
                    final = message
    finally:
        release_processes(held)
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
