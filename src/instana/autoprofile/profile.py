# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import math
import os
import time
import uuid
from typing import Any, Dict, Optional


class Profile(object):
    CATEGORY_CPU = "cpu"
    CATEGORY_MEMORY = "memory"
    CATEGORY_TIME = "time"
    TYPE_CPU_USAGE = "cpu-usage"
    TYPE_MEMORY_ALLOCATION_RATE = "memory-allocation-rate"
    TYPE_BLOCKING_CALLS = "blocking-calls"
    UNIT_NONE = ""
    UNIT_MILLISECOND = "millisecond"
    UNIT_MICROSECOND = "microsecond"
    UNIT_NANOSECOND = "nanosecond"
    UNIT_BYTE = "byte"
    UNIT_KILOBYTE = "kilobyte"
    UNIT_PERCENT = "percent"
    UNIT_SAMPLE = "sample"
    RUNTIME_PYTHON = "python"

    def __init__(
        self,
        category: str,
        typ: str,
        unit: str,
        roots: object,
        duration: int,
        timespan: int,
    ) -> None:
        self.process_id = str(os.getpid())
        self.id = generate_uuid()
        self.runtime = Profile.RUNTIME_PYTHON
        self.category = category
        self.type = typ
        self.unit = unit
        self.roots = roots
        self.duration = duration
        self.timespan = timespan
        self.timestamp = millis()

    def to_dict(self) -> Dict[str, Any]:
        profile_dict = {
            "pid": self.process_id,
            "id": self.id,
            "runtime": self.runtime,
            "category": self.category,
            "type": self.type,
            "unit": self.unit,
            "roots": [root.to_dict() for root in self.roots],
            "duration": self.duration,
            "timespan": self.timespan,
            "timestamp": self.timestamp,
        }

        return profile_dict


class CallSite:
    __slots__ = [
        "method_name",
        "file_name",
        "file_line",
        "measurement",
        "num_samples",
        "children",
    ]

    def __init__(self, method_name: str, file_name: str, file_line: int) -> None:
        self.method_name = method_name
        self.file_name = file_name
        self.file_line = file_line
        self.measurement: int = 0
        self.num_samples: int = 0
        self.children = dict()

    def create_key(self, method_name: str, file_name: str, file_line: int) -> str:
        return f"{method_name} ({file_name}:{file_line})"

    def find_child(
        self, method_name: str, file_name: str, file_line: int
    ) -> Optional[object]:
        key = self.create_key(method_name, file_name, file_line)
        if key in self.children:
            return self.children[key]

        return None

    def add_child(self, child: object) -> None:
        self.children[
            self.create_key(child.method_name, child.file_name, child.file_line)
        ] = child

    def remove_child(self, child: object) -> None:
        del self.children[
            self.create_key(child.method_name, child.file_name, child.file_line)
        ]

    def find_or_add_child(
        self, method_name: str, file_name: str, file_line: int
    ) -> object:
        child = self.find_child(method_name, file_name, file_line)
        if not child:
            child = CallSite(method_name, file_name, file_line)
            self.add_child(child)

        return child

    def increment(self, value: int, count: int) -> None:
        self.measurement += value
        self.num_samples += count

    def normalize(self, factor: int) -> None:
        self.measurement = self.measurement / factor
        self.num_samples = int(math.ceil(self.num_samples / factor))

        for child in self.children.values():
            child.normalize(factor)

    def floor(self) -> None:
        self.measurement = int(self.measurement)

        for child in self.children.values():
            child.floor()

    def to_dict(self) -> Dict[str, Any]:
        children_dicts = []
        for child in self.children.values():
            children_dicts.append(child.to_dict())

        call_site_dict = {
            "method_name": self.method_name,
            "file_name": self.file_name,
            "file_line": self.file_line,
            "measurement": self.measurement,
            "num_samples": self.num_samples,
            "children": children_dicts,
        }

        return call_site_dict


def millis() -> int:
    """
    Returns the current time in milliseconds since the Unix epoch (January 1, 1970).
    """
    return int(round(time.time() * 1000))


def generate_uuid() -> str:
    """
    Generates a UUID as string.
    """
    return str(uuid.uuid4())
