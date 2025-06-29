# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import platform

os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

# ppc64le is not supported by AWS Serverless Services.
collect_ignore_glob = []
if platform.machine() == "ppc64le":
    collect_ignore_glob.append("*test_lambda*")
    collect_ignore_glob.append("*test_fargate*")
    collect_ignore_glob.append("*test_eks*")