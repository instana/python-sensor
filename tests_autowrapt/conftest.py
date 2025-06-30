# (c) Copyright IBM Corp. 2025

import os

collect_ignore_glob = []
if not os.environ.get("AUTOWRAPT_BOOTSTRAP", None):
    collect_ignore_glob.append("*test_autowrapt*")
