# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import time
import random
from typing import Union

from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID, INVALID_TRACE_ID

_rnd = random.Random()
_current_pid = 0


def generate_id() -> int:
    """Get a new ID.

    Returns:
        A 64-bit int for use as a Span or Trace ID.
    """
    global _current_pid

    pid = os.getpid()
    if _current_pid != pid:
        _current_pid = pid
        _rnd.seed(int(1000000 * time.time()) ^ pid)
    new_id = _rnd.randint(0, _SPAN_ID_MAX_VALUE)

    return new_id


def header_to_long_id(header: Union[bytes, str]) -> int:
    """
    We can receive headers in the following formats:
      1. unsigned base 16 hex string (or bytes) of variable length
      2. [eventual]

    :param header: the header to analyze, validate and convert (if needed)
    :return: a valid ID to be used internal to the tracer
    """
    if isinstance(header, bytes):
        header = header.decode('utf-8')

    if not isinstance(header, str):
        return INVALID_TRACE_ID

    if header.isdecimal():
        return header

    try:
        if len(header) < 16:
            # Left pad ID with zeros
            header = header.zfill(16)

        return int(header, 16)
    except ValueError:
        return INVALID_TRACE_ID


def header_to_id(header: Union[bytes, str]) -> int:
    """
    We can receive headers in the following formats:
      1. unsigned base 16 hex string (or bytes) of variable length
      2. [eventual]

    :param header: the header to analyze, validate and convert (if needed)
    :return: a valid ID to be used internal to the tracer
    """
    if isinstance(header, bytes):
        header = header.decode('utf-8')

    if not isinstance(header, str):
        return INVALID_SPAN_ID

    if header.isdecimal():
        return header

    try:
        length = len(header)
        if length < 16:
            # Left pad ID with zeros
            header = header.zfill(16)
        elif length > 16:
            # Phase 0: Discard everything but the last 16byte
            header = header[-16:]

        return int(header, 16)
    except ValueError:
        return INVALID_SPAN_ID


def hex_id(id: Union[int, str]) -> str:
    """
    Returns the hexadecimal representation of the given ID.
    """

    hex_id = hex(int(id))[2:]
    if len(hex_id) < 16:
        hex_id = hex_id.zfill(16)
    elif len(hex_id) > 16 and len(hex_id) < 32:
        hex_id = hex_id.zfill(32)
    return hex_id

def hex_id_16(id: Union[int, str]) -> str:
    """
    Returns the hexadecimal representation of the given ID.
    """
    try:
        hex_id = hex(int(id))[2:]
        length = len(hex_id)
        if length < 16:
            hex_id = hex_id.zfill(16)
        elif length > 16:
            # Phase 0: Discard everything but the last 16byte
            hex_id = hex_id[-16:]
        return hex_id
    except Exception: # ValueError: invalid literal for int() with base 10:
        return id

def define_server_timing(trace_id: Union[int, str]) -> str:
    # Note: The key `intid` is short for Instana Trace ID.
    return f"intid;desc={hex_id_16(trace_id)}"


def header_to_32(header) -> int:
    if isinstance(header, int):
        return header

    try:
        if len(header) < 16:
            # Left pad ID with zeros
            header = header.zfill(16)

        return int(header, 16)
    except ValueError:
        return INVALID_TRACE_ID
    
def header_to_16(header) -> int:
    if isinstance(header, int):
        return header

    try:
        length = len(header)
        if length < 16:
            # Left pad ID with zeros
            header = header.zfill(16)
        elif length > 16:
            # Phase 0: Discard everything but the last 16byte
            header = header[-16:]

        return int(header, 16)
    except ValueError:
        return INVALID_SPAN_ID