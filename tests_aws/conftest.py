# (c) Copyright IBM Corp. 2024

import os
import platform

os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

# ppc64le and s390x are not supported by AWS Serverless Services.
collect_ignore_glob = []
if platform.machine() in ["ppc64le", "s390x"]:
    collect_ignore_glob.extend([
        "*test_lambda*",
        "*test_fargate*",
        "*test_eks*",
    ])
    