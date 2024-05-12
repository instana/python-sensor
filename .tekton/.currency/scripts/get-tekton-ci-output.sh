#!/bin/bash

TEKTON_CI_OUT_FILE=resources/tekton-ci-output.txt

successful_taskruns=( $(kubectl get taskrun --sort-by=.metadata.creationTimestamp | grep "^python-trace\w*-unittest-default-3" | grep -v "pr\|Failed" | awk '{print $1}') )

for ((i=${#successful_taskruns[@]}-1; i>=0; i--)); do
    pod_name=$(kubectl get taskrun "${successful_taskruns[$i]}" -o jsonpath='{.status.podName}')
    ci_output=$(kubectl logs ${pod_name} -c step-unittest | grep "Successfully installed")
    if [ -n "${ci_output}" ]; then
        latest_successful_taskrun_pod=$pod_name
        break
    fi
done
  
kubectl logs ${latest_successful_taskrun_pod} -c step-unittest | grep "Successfully installed" > ${TEKTON_CI_OUT_FILE}
