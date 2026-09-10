# Keep all relay descendants inside a job whose lifetime is the task's launcher.
# No breakaway permission: task cancellation/timeout also stops Python/SSH children.
if (-not ('Smako.RelayProcessLifetime' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
namespace Smako {
    public static class RelayProcessLifetime {
        private static IntPtr job = IntPtr.Zero;
        [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
            public long ProcessTime, JobTime;
            public uint Flags;
            public UIntPtr MinWorkingSet, MaxWorkingSet;
            public uint ActiveProcesses;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }
        [StructLayout(LayoutKind.Sequential)] struct IoCounters {
            public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        }
        [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
            public BasicLimits Basic;
            public IoCounters Io;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        static extern IntPtr CreateJobObject(IntPtr attributes, string name);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool SetInformationJobObject(IntPtr job, int kind, ref ExtendedLimits limits, uint size);
        [DllImport("kernel32.dll", SetLastError=true)]
        static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
        public static void Bind() {
            if (job != IntPtr.Zero) return;
            IntPtr candidate = CreateJobObject(IntPtr.Zero, null);
            if (candidate == IntPtr.Zero) throw new Win32Exception();
            ExtendedLimits limits = new ExtendedLimits();
            limits.Basic.Flags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if (!SetInformationJobObject(candidate, 9, ref limits, (uint)Marshal.SizeOf(limits)) ||
                !AssignProcessToJobObject(candidate, GetCurrentProcess())) {
                int error = Marshal.GetLastWin32Error();
                CloseHandle(candidate);
                throw new Win32Exception(error);
            }
            // Deliberately retained until launcher exit; never inherited by children.
            job = candidate;
        }
    }
}
'@
}
[Smako.RelayProcessLifetime]::Bind()
