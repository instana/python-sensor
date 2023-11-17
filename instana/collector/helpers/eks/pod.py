# (c) Copyright IBM Corp. 2023

""" Module to handle the collection of container metrics for EKS Pods on AWS Fargate """
import os
import re
from instana.log import logger


def get_pod_name():
    podname = os.environ.get('HOSTNAME')

    if not podname:
        logger.warning("Failed to determine podname from EKS hostname.")
    return podname
