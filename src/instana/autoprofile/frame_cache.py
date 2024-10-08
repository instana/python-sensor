# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instana.autoprofile.profile import Profile


class FrameCache(object):
    MAX_CACHE_SIZE = 2500

    def __init__(self, profiler: "Profile") -> None:
        self.profiler = profiler
        self.profiler_frame_cache = None
        self.include_profiler_frames = None
        self.profiler_dir = os.path.dirname(os.path.realpath(__file__))

    def start(self) -> None:
        self.profiler_frame_cache = dict()
        self.include_profiler_frames = self.profiler.get_option(
            "include_profiler_frames", False
        )

    def stop(self) -> None:
        pass

    def is_profiler_frame(self, filename: str) -> bool:
        if filename in self.profiler_frame_cache:
            return self.profiler_frame_cache[filename]

        profiler_frame = False

        if not self.include_profiler_frames:
            if filename.startswith(self.profiler_dir):
                profiler_frame = True

        if len(self.profiler_frame_cache) < self.MAX_CACHE_SIZE:
            self.profiler_frame_cache[filename] = profiler_frame

        return profiler_frame
