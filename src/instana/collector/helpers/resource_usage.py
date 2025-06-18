# (c) Copyright IBM Corp. 2025

"""Cross-platform resource usage information"""

import os
from typing import NamedTuple

from instana.log import logger
from instana.util.runtime import is_windows


class ResourceUsage(NamedTuple):
    """
    Cross-platform resource usage information, mirroring fields found in the Unix rusage struct.

    Attributes:
        ru_utime (float): User CPU time used (seconds).
        ru_stime (float): System CPU time used (seconds).
        ru_maxrss (int): Maximum resident set size used (bytes).
        ru_ixrss (int): Integral shared memory size (bytes).
        ru_idrss (int): Integral unshared data size (bytes).
        ru_isrss (int): Integral unshared stack size (bytes).
        ru_minflt (int): Number of page reclaims (soft page faults).
        ru_majflt (int): Number of page faults requiring I/O (hard page faults).
        ru_nswap (int): Number of times a process was swapped out.
        ru_inblock (int): Number of file system input blocks.
        ru_oublock (int): Number of file system output blocks.
        ru_msgsnd (int): Number of messages sent.
        ru_msgrcv (int): Number of messages received.
        ru_nsignals (int): Number of signals received.
        ru_nvcsw (int): Number of voluntary context switches.
        ru_nivcsw (int): Number of involuntary context switches.
    """

    ru_utime: float = 0.0
    ru_stime: float = 0.0
    ru_maxrss: int = 0
    ru_ixrss: int = 0
    ru_idrss: int = 0
    ru_isrss: int = 0
    ru_minflt: int = 0
    ru_majflt: int = 0
    ru_nswap: int = 0
    ru_inblock: int = 0
    ru_oublock: int = 0
    ru_msgsnd: int = 0
    ru_msgrcv: int = 0
    ru_nsignals: int = 0
    ru_nvcsw: int = 0
    ru_nivcsw: int = 0


def get_resource_usage() -> ResourceUsage:
    """Get resource usage in a cross-platform way"""
    if is_windows():
        return _get_windows_resource_usage()
    else:
        return _get_unix_resource_usage()


def _get_unix_resource_usage() -> ResourceUsage:
    """Get resource usage on Unix systems"""
    import resource

    rusage = resource.getrusage(resource.RUSAGE_SELF)

    return ResourceUsage(
        ru_utime=rusage.ru_utime,
        ru_stime=rusage.ru_stime,
        ru_maxrss=rusage.ru_maxrss,
        ru_ixrss=rusage.ru_ixrss,
        ru_idrss=rusage.ru_idrss,
        ru_isrss=rusage.ru_isrss,
        ru_minflt=rusage.ru_minflt,
        ru_majflt=rusage.ru_majflt,
        ru_nswap=rusage.ru_nswap,
        ru_inblock=rusage.ru_inblock,
        ru_oublock=rusage.ru_oublock,
        ru_msgsnd=rusage.ru_msgsnd,
        ru_msgrcv=rusage.ru_msgrcv,
        ru_nsignals=rusage.ru_nsignals,
        ru_nvcsw=rusage.ru_nvcsw,
        ru_nivcsw=rusage.ru_nivcsw,
    )


def _get_windows_resource_usage() -> ResourceUsage:
    """Get resource usage on Windows systems"""
    # On Windows, we can use psutil to get some of the metrics
    # For metrics that aren't available, we return 0
    try:
        import psutil

        process = psutil.Process(os.getpid())

        # Get CPU times
        cpu_times = process.cpu_times()

        # Get memory info
        memory_info = process.memory_info()

        # Get IO counters
        io_counters = process.io_counters() if hasattr(process, "io_counters") else None

        # Get context switch counts if available
        ctx_switches = (
            process.num_ctx_switches() if hasattr(process, "num_ctx_switches") else None
        )

        return ResourceUsage(
            ru_utime=cpu_times.user if hasattr(cpu_times, "user") else 0.0,
            ru_stime=cpu_times.system if hasattr(cpu_times, "system") else 0.0,
            ru_maxrss=memory_info.rss // 1024
            if hasattr(memory_info, "rss")
            else 0,  # Convert to KB to match Unix
            ru_ixrss=0,  # Not available on Windows
            ru_idrss=0,  # Not available on Windows
            ru_isrss=0,  # Not available on Windows
            ru_minflt=0,  # Not directly available on Windows
            ru_majflt=0,  # Not directly available on Windows
            ru_nswap=0,  # Not available on Windows
            ru_inblock=io_counters.read_count
            if io_counters and hasattr(io_counters, "read_count")
            else 0,
            ru_oublock=io_counters.write_count
            if io_counters and hasattr(io_counters, "write_count")
            else 0,
            ru_msgsnd=0,  # Not available on Windows
            ru_msgrcv=0,  # Not available on Windows
            ru_nsignals=0,  # Not available on Windows
            ru_nvcsw=ctx_switches.voluntary
            if ctx_switches and hasattr(ctx_switches, "voluntary")
            else 0,
            ru_nivcsw=ctx_switches.involuntary
            if ctx_switches and hasattr(ctx_switches, "involuntary")
            else 0,
        )
    except ImportError:
        # If psutil is not available, return zeros
        logger.debug(
            "get_windows_resource_usage: psutil is not available, returning zeros"
        )
        return ResourceUsage()


# Made with Bob
