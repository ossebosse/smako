"""One serial, bounded Python check against the shared intake/V2 wall budget.

An interrupted open entry is charged through the next invocation; no new budget
is created by a new command or report. Never starts a continuation worker.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import runpy
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


def windows_limits():
    """Windows job commit accounting differs from Linux cgroup/RSS evidence."""
    if os.name != "nt":
        raise RuntimeError("This local verifier requires the documented Windows job limits")
    from ctypes import wintypes as w

    size = ctypes.c_size_t

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", w.DWORD), ("min_working", size), ("max_working", size),
                    ("active", w.DWORD), ("affinity", size), ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

    class Limits(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size), ("job_memory", size),
                    ("peak_process_memory", size), ("peak_job_memory", size)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.GetProcessAffinityMask.argtypes = [w.HANDLE, ctypes.POINTER(size), ctypes.POINTER(size)]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    job = kernel.CreateJobObjectW(None, None)
    process_mask, system_mask = size(), size()
    if not job or not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise ctypes.WinError(ctypes.get_last_error())
    bits = [1 << n for n in range(64) if process_mask.value & (1 << n)]
    if len(bits) < 2:
        raise RuntimeError("Two processors unavailable")
    limits = Limits()
    limits.basic.flags = 0x200 | 0x10 | 0x2000  # memory, affinity, kill on runner exit
    limits.basic.affinity = bits[0] | bits[1]
    limits.job_memory = 3 * 1024**3
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())

    def attach(process):
        if not kernel.AssignProcessToJobObject(job, w.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())

    def peak():
        if not kernel.QueryInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return limits.peak_job_memory

    class Memory(ctypes.Structure):
        _fields_ = [("cb", w.DWORD), ("faults", w.DWORD)] + [(name, size) for name in (
            "peak_working", "working", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
            "pagefile", "peak_pagefile", "private")]

    kernel.K32GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]

    def sample(process):
        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        if kernel.K32GetProcessMemoryInfo(w.HANDLE(int(process._handle)), ctypes.byref(memory), memory.cb):
            return memory.peak_working, memory.peak_pagefile
        return 0, 0

    return attach, peak, sample, lambda: kernel.TerminateJobObject(job, 124)


def run(args):
    args.budget = args.budget.resolve()
    budget = json.loads(args.budget.read_bytes())
    now = datetime.now(UTC)
    for entry in budget["entries"]:
        if entry.get("status") == "running":
            entry.update(status="interrupted_charged", wall_seconds=(now - datetime.fromisoformat(entry["started_at"])).total_seconds())
    used = budget.get("prior_v2_seconds", 0) + sum(e["wall_seconds"] for e in budget["entries"])
    remaining = budget["limit_seconds"] - used
    if remaining <= 0:
        raise RuntimeError("Shared qualification/benchmark budget exhausted")
    entry = {"label": args.label, "started_at": now.isoformat(), "wall_seconds": 0, "status": "running",
             "environment": "Windows job: two processor affinity, 3 GiB commit limit; not Linux cgroup latency"}
    budget["entries"].append(entry)

    def save():
        charged = budget.get("prior_v2_seconds", 0) + sum(e["wall_seconds"] for e in budget["entries"])
        budget.update(used_seconds=charged, remaining_seconds=budget["limit_seconds"] - charged,
                      phase_status="serial check running" if entry["status"] == "running"
                      else "check closed; same shared budget remains for intake/V2")
        temporary = args.budget.with_suffix(".next")
        temporary.write_text(json.dumps(budget, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.budget)

    save()
    start = time.perf_counter()
    code = 1
    cancel = threading.Event()
    worker = SimpleNamespace(_handle=-1)  # Actual interpreter, including Store-Python launchers.
    deadline = start + min(args.max_seconds, remaining)
    try:
        attach, peak, sample, _terminate = windows_limits()
        attach(worker)
        entry["resource_enforcement"] = "actual_interpreter_self_attached"
        save()

        def receipt():
            working, private = sample(worker)
            entry.update(peak_job_commit_bytes=peak(), peak_working_bytes=working,
                         peak_private_commit_bytes=private, wall_seconds=round(time.perf_counter() - start, 4))

        def watchdog():
            if not cancel.wait(max(0, deadline - time.perf_counter())):
                entry.update(exit_code=124, status="deadline_exceeded")
                receipt()
                save()
                os._exit(124)

        threading.Thread(target=watchdog, daemon=True).start()
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if command[:2] == ["-X", "utf8"]:
            command = command[2:]
        os.environ["PYTHON_DOTENV_DISABLED"] = "1"
        # Run in this interpreter: the Windows Store venv launcher may otherwise
        # delegate to a process outside the wrapper's job. No subprocess gap.
        sys.argv = command[1:] if command[:1] == ["-m"] else command
        try:
            if command[:1] == ["-m"]:
                runpy.run_module(command[1], run_name="__main__", alter_sys=True)
            else:
                runpy.run_path(command[0], run_name="__main__")
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0 if exc.code is None else 1
        entry.update(exit_code=code, status="complete" if code == 0 else "stopped")
        receipt()
        return code
    finally:
        cancel.set()
        entry["wall_seconds"] = round(time.perf_counter() - start, 4)
        if entry["status"] == "running":
            entry["status"] = "failed"
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--max-seconds", type=float, default=75)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    raise SystemExit(run(parser.parse_args()))
