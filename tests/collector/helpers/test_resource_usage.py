# (c) Copyright IBM Corp. 2025


import pytest

from instana.collector.helpers.resource_usage import (
    ResourceUsage,
    _get_unix_resource_usage,
    _get_windows_resource_usage,
    get_resource_usage,
)
from instana.util.runtime import is_windows


class TestResourceUsage:
    def test_resource_usage_namedtuple_defaults(self):
        """Test that ResourceUsage has proper default values"""
        usage = ResourceUsage()
        assert usage.ru_utime == 0.0
        assert usage.ru_stime == 0.0
        assert usage.ru_maxrss == 0
        assert usage.ru_ixrss == 0
        assert usage.ru_idrss == 0
        assert usage.ru_isrss == 0
        assert usage.ru_minflt == 0
        assert usage.ru_majflt == 0
        assert usage.ru_nswap == 0
        assert usage.ru_inblock == 0
        assert usage.ru_oublock == 0
        assert usage.ru_msgsnd == 0
        assert usage.ru_msgrcv == 0
        assert usage.ru_nsignals == 0
        assert usage.ru_nvcsw == 0
        assert usage.ru_nivcsw == 0

    def test_resource_usage_namedtuple_custom_values(self):
        """Test that ResourceUsage can be initialized with custom values"""
        usage = ResourceUsage(
            ru_utime=1.0,
            ru_stime=2.0,
            ru_maxrss=3,
            ru_ixrss=4,
            ru_idrss=5,
            ru_isrss=6,
            ru_minflt=7,
            ru_majflt=8,
            ru_nswap=9,
            ru_inblock=10,
            ru_oublock=11,
            ru_msgsnd=12,
            ru_msgrcv=13,
            ru_nsignals=14,
            ru_nvcsw=15,
            ru_nivcsw=16,
        )
        assert usage.ru_utime == 1.0
        assert usage.ru_stime == 2.0
        assert usage.ru_maxrss == 3
        assert usage.ru_ixrss == 4
        assert usage.ru_idrss == 5
        assert usage.ru_isrss == 6
        assert usage.ru_minflt == 7
        assert usage.ru_majflt == 8
        assert usage.ru_nswap == 9
        assert usage.ru_inblock == 10
        assert usage.ru_oublock == 11
        assert usage.ru_msgsnd == 12
        assert usage.ru_msgrcv == 13
        assert usage.ru_nsignals == 14
        assert usage.ru_nvcsw == 15
        assert usage.ru_nivcsw == 16

    @pytest.mark.skipif(
        is_windows(),
        reason="Avoiding Unix resource usage collection on Windows systems.",
    )
    def test_get_resource_usage_unix(self):
        """Test that get_resource_usage calls _get_unix_resource_usage on Unix-like systems."""
        usage = get_resource_usage()

        assert usage.ru_utime >= 0.0
        assert usage.ru_stime >= 0.0
        assert usage.ru_maxrss >= 0
        assert usage.ru_ixrss >= 0
        assert usage.ru_idrss >= 0
        assert usage.ru_isrss >= 0
        assert usage.ru_minflt >= 0
        assert usage.ru_majflt >= 0
        assert usage.ru_nswap >= 0
        assert usage.ru_inblock >= 0
        assert usage.ru_oublock >= 0
        assert usage.ru_msgsnd >= 0
        assert usage.ru_msgrcv >= 0
        assert usage.ru_nsignals >= 0
        assert usage.ru_nvcsw >= 0
        assert usage.ru_nivcsw >= 0

    @pytest.mark.skipif(
        not is_windows(),
        reason="Avoiding Windows resource usage collection on Unix-like systems.",
    )
    def test_get_resource_usage_windows(self):
        """Test that get_resource_usage calls _get_windows_resource_usage on Windows systems"""
        usage = get_resource_usage()

        assert usage.ru_utime >= 0.0
        assert usage.ru_stime >= 0.0
        assert usage.ru_maxrss >= 0
        assert usage.ru_ixrss == 0
        assert usage.ru_idrss == 0
        assert usage.ru_isrss == 0
        assert usage.ru_minflt == 0
        assert usage.ru_majflt == 0
        assert usage.ru_nswap == 0
        assert usage.ru_inblock >= 0
        assert usage.ru_oublock >= 0
        assert usage.ru_msgsnd == 0
        assert usage.ru_msgrcv == 0
        assert usage.ru_nsignals == 0
        assert usage.ru_nvcsw >= 0
        assert usage.ru_nivcsw >= 0

    @pytest.mark.skipif(
        is_windows(),
        reason="Avoiding Unix resource usage collection on Windows. systems",
    )
    def test_get_unix_resource_usage(self):
        """Test _get_unix_resource_usage function"""
        usage = _get_unix_resource_usage()

        assert usage.ru_utime >= 0.0
        assert usage.ru_stime >= 0.0
        assert usage.ru_maxrss >= 0
        assert usage.ru_ixrss >= 0
        assert usage.ru_idrss >= 0
        assert usage.ru_isrss >= 0
        assert usage.ru_minflt >= 0
        assert usage.ru_majflt >= 0
        assert usage.ru_nswap >= 0
        assert usage.ru_inblock >= 0
        assert usage.ru_oublock >= 0
        assert usage.ru_msgsnd >= 0
        assert usage.ru_msgrcv >= 0
        assert usage.ru_nsignals >= 0
        assert usage.ru_nvcsw >= 0
        assert usage.ru_nivcsw >= 0

    @pytest.mark.skipif(
        not is_windows(),
        reason="Avoiding Windows resource usage collection on Unix-like systems.",
    )
    def test_get_windows_resource_usage_with_psutil(self):
        """Test _get_windows_resource_usage function with psutil available"""
        usage = _get_windows_resource_usage()

        assert usage.ru_utime >= 0.0
        assert usage.ru_stime >= 0.0
        assert usage.ru_maxrss >= 0
        assert usage.ru_ixrss == 0
        assert usage.ru_idrss == 0
        assert usage.ru_isrss == 0
        assert usage.ru_minflt == 0
        assert usage.ru_majflt == 0
        assert usage.ru_nswap == 0
        assert usage.ru_inblock >= 0
        assert usage.ru_oublock >= 0
        assert usage.ru_msgsnd == 0
        assert usage.ru_msgrcv == 0
        assert usage.ru_nsignals == 0
        assert usage.ru_nvcsw >= 0
        assert usage.ru_nivcsw >= 0

    @pytest.mark.skipif(
        not is_windows(),
        reason="Avoiding Windows resource usage collection on Unix-like systems.",
    )
    def test_get_windows_resource_usage_without_psutil(self, mocker):
        """Test _get_windows_resource_usage function when psutil is not available"""

        mocker.patch("psutil.Process", side_effect=ImportError)
        result = _get_windows_resource_usage()

        # Should return default ResourceUsage with all zeros
        assert result.ru_utime == 0.0
        assert result.ru_stime == 0.0
        assert result.ru_maxrss == 0
        assert result.ru_ixrss == 0
        assert result.ru_idrss == 0
        assert result.ru_isrss == 0
        assert result.ru_minflt == 0
        assert result.ru_majflt == 0
        assert result.ru_nswap == 0
        assert result.ru_inblock == 0
        assert result.ru_oublock == 0
        assert result.ru_msgsnd == 0
        assert result.ru_msgrcv == 0
        assert result.ru_nsignals == 0
        assert result.ru_nvcsw == 0
        assert result.ru_nivcsw == 0


# Made with Bob
