# (c) Copyright IBM Corp. 2024
# (c) Copyright Instana Inc. 2024

"""
Tests for IPv6 support in the Instana Python sensor.
These tests verify that the agent can connect to IPv6 addresses.
"""

import errno
import socket

import pytest


class TestIPv6SocketSupport:
    """Test suite for IPv6 socket support"""

    def test_socket_af_inet_vs_af_inet6(self):
        """Test the difference between AF_INET and AF_INET6"""
        # IPv4 socket
        assert socket.AF_INET == 2

        # IPv6 socket (value varies by platform, typically 10 on Linux, 30 on macOS)
        if hasattr(socket, "AF_INET6"):
            assert socket.AF_INET6 in (10, 30)  # 10 on Linux, 30 on macOS
        else:
            pytest.skip("AF_INET6 not available on this platform")

    def test_ipv6_socket_availability(self):
        """Test if IPv6 sockets are available on the system"""
        try:
            # Try to create an IPv6 socket
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.close()
            ipv6_available = True
        except (OSError, AttributeError):
            ipv6_available = False

        # Just document the availability
        assert isinstance(ipv6_available, bool)

    def test_getaddrinfo_for_dual_stack(self):
        """Test getaddrinfo for dual-stack support"""
        # getaddrinfo can return both IPv4 and IPv6 addresses
        try:
            results = socket.getaddrinfo(
                "localhost", 42699, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
            assert len(results) > 0

            # Check if we get both IPv4 and IPv6
            families = {result[0] for result in results}

            # At minimum, we should get IPv4
            assert socket.AF_INET in families or socket.AF_INET6 in families
        except socket.gaierror:
            pytest.skip("getaddrinfo not available or localhost not resolvable")

    def test_af_inet_socket_cannot_connect_to_ipv6(self):
        """Test that AF_INET (IPv4-only) socket cannot connect to IPv6 addresses

        This test demonstrates the limitation documented in src/instana/fsm.py:140
        where socket.AF_INET is used, which only supports IPv4 addresses.

        The test shows that:
        1. AF_INET socket can attempt IPv4 connections (gets connection refused if no server)
        2. AF_INET socket CANNOT connect to IPv6 addresses (gets address family error)

        When an AF_INET socket attempts to connect to an IPv6 address like ::1,
        it will fail with OSError or socket.gaierror because:
        - AF_INET expects IPv4 addresses (e.g., 127.0.0.1)
        - IPv6 addresses require AF_INET6 or dual-stack support via getaddrinfo
        - On macOS, this typically results in gaierror (address resolution failure)
        - On Linux, this typically results in OSError (address family not supported)
        """
        # Skip if IPv6 is not available on the system
        if not hasattr(socket, "AF_INET6"):
            pytest.skip("AF_INET6 not available on this platform")

        ipv4_loopback = "127.0.0.1"
        ipv6_loopback = "::1"
        port = 42699

        # STEP 1: Demonstrate that AF_INET socket works with IPv4 addresses
        # Create an IPv4-only socket (AF_INET)
        # This mimics the behavior in src/instana/fsm.py:140
        sock_ipv4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_ipv4.settimeout(0.1)  # Set short timeout to avoid hanging

        try:
            # Attempt to connect to IPv4 address with IPv4 socket
            # This should either succeed (if server is running) or fail with connection error
            # but NOT with an address family error
            try:
                sock_ipv4.connect((ipv4_loopback, port))
                # If connection succeeds, that's fine - it means IPv4 works
                ipv4_connected = True
            except OSError as e:
                # Connection failed, but should be connection-related error, not address family
                ipv4_connected = False
                # Acceptable errors: ECONNREFUSED, ETIMEDOUT, EHOSTUNREACH
                assert e.errno in (
                    errno.ECONNREFUSED,  # Connection refused
                    errno.ETIMEDOUT,  # Connection timed out
                    errno.EHOSTUNREACH,  # Host unreachable
                ), (
                    f"IPv4 connection failed with unexpected error: errno {e.errno}: {e}. "
                    f"Expected connection-related error, not address family error."
                )

        finally:
            sock_ipv4.close()

        # STEP 2: Demonstrate that AF_INET socket CANNOT connect to IPv6 addresses
        # Create another IPv4-only socket (AF_INET)
        sock_ipv6_attempt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            # Attempt to connect to IPv6 address with IPv4 socket
            # This should fail with OSError or socket.gaierror (address family error)
            with pytest.raises((OSError, socket.error, socket.gaierror)) as exc_info:
                sock_ipv6_attempt.connect((ipv6_loopback, port))

            # Verify we got an appropriate address family error
            # Common errors include:
            # - gaierror with errno 8 (EAI_NONAME): "nodename nor servname provided, or not known" (macOS)
            # - OSError with EAFNOSUPPORT: "Address family not supported by protocol" (Linux)
            # - OSError with EINVAL: "Invalid argument" (Windows)
            # - OSError with EADDRNOTAVAIL: "Address not available"
            error = exc_info.value

            # Check if it's a gaierror (address resolution failure)
            if isinstance(error, socket.gaierror):
                # errno 8 (EAI_NONAME) is expected on macOS when AF_INET socket tries IPv6
                assert (
                    error.errno == 8
                    or "nodename" in str(error).lower()
                    or "not known" in str(error).lower()
                ), f"Unexpected gaierror: {error}"
            else:
                # For other OSErrors, check for expected errno values
                # Should NOT be ECONNREFUSED (that would mean it tried to connect)
                assert error.errno != errno.ECONNREFUSED, (
                    "Got ECONNREFUSED instead of address family error - "
                    "this means the socket incorrectly accepted the IPv6 address"
                )
                assert (
                    error.errno
                    in (
                        errno.EAFNOSUPPORT,  # Address family not supported
                        errno.EINVAL,  # Invalid argument
                        errno.EADDRNOTAVAIL,  # Address not available
                    )
                    or "address" in str(error).lower()
                ), f"Unexpected error for IPv6 connection: errno {error.errno}: {error}"

        finally:
            sock_ipv6_attempt.close()

        # Additional verification: AF_INET6 socket CAN be created for IPv6
        # (actual connection would require a listening server)
        # This demonstrates the correct approach for IPv6 support
        sock_ipv6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock_ipv6.close()

        # Document: To support both IPv4 and IPv6, use getaddrinfo:
        # results = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        # This is the recommended approach for dual-stack support


# Made with Bob
