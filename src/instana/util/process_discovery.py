# (c) Copyright IBM Corp. 2025

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Discovery:
    pid: int = 0  # the PID of this process
    name: Optional[str] = None  # the name of the executable
    args: Optional[List[str]] = None  # the command line arguments
    fd: int = -1  # the file descriptor of the socket associated with the connection to the agent for this HTTP request
    inode: str = ""  # the inode of the socket associated with the connection to the agent for this HTTP request
