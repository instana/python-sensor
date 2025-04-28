import os
import sys

def test_autowrapt_bootstrap():
    assert os.environ.get("AUTOWRAPT_BOOTSTRAP") == "instana"
    assert "instana" in sys.modules
