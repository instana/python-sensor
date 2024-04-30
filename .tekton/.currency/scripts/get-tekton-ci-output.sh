#!/bin/bash

TEKTON_CI_OUT_FILE=utils/tekton-ci-output.txt

latest_successful_taskrun=$(kubectl get taskrun --sort-by=.metadata.creationTimestamp | grep "^python-trace\w[^-]\w*-unittest-default-3" | grep -v Failed | tail -n 1 | awk '{print $1}')
pod_name=$(kubectl get taskrun "$latest_successful_taskrun" -o jsonpath='{.status.podName}')
kubectl logs $pod_name -c step-unittest | grep "Successfully installed" >> ${TEKTON_CI_OUT_FILE}
