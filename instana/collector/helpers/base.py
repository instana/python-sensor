# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Base class for the various helpers that can be used by Collectors.  Helpers assist
in the data collection for various entities such as host, hardware, AWS Task, ec2,
memory, cpu, docker etc etc..
"""
from ...log import logger


class BaseHelper(object):
    """
    Base class for all helpers.  Descendants must override and implement `self.collect_metrics`.
    """
    def __init__(self, collector):
        self.collector = collector

    def get_delta(self, source, previous, metric):
        """
        Given a metric, see if the value varies from the previous reported metrics

        @param source [dict or value]: the dict to retrieve the new value of <metric> (as source[metric]) or
          if not a dict, then the new value of the metric
        @param previous [dict]: the previous value of <metric> that was reported (as previous[metric])
        @param metric [String or Tuple]: the name of the metric in question.  If the keys for source[metric],
          and previous[metric] vary, you can pass a tuple in the form of (src, dst)
        @return: None (meaning no difference) or the new value (source[metric])
        """
        if isinstance(metric, tuple):
            src_metric = metric[0]
            dst_metric = metric[1]
        else:
            src_metric = metric
            dst_metric = metric

        if isinstance(source, dict):
            new_value = source.get(src_metric, None)
        else:
            new_value = source

        if previous[dst_metric] != new_value:
            return new_value
        else:
            return None

    def apply_delta(self, source, previous, new, metric, with_snapshot):
        """
        Helper method to assist in delta reporting of metrics.

        @param source [dict or value]: the dict to retrieve the new value of <metric> (as source[metric]) or
          if not a dict, then the new value of the metric
        @param previous [dict]: the previous value of <metric> that was reported (as previous[metric])
        @param new [dict]: the new value of the metric that will be sent new (as new[metric])
        @param metric [String or Tuple]: the name of the metric in question.  If the keys for source[metric],
          previous[metric] and new[metric] vary, you can pass a tuple in the form of (src, dst)
        @param with_snapshot [Bool]: if this metric is being sent with snapshot data
        @return: None
        """
        if isinstance(metric, tuple):
            src_metric = metric[0]
            dst_metric = metric[1]
        else:
            src_metric = metric
            dst_metric = metric

        if isinstance(source, dict):
            new_value = source.get(src_metric, None)
        else:
            new_value = source

        previous_value = previous.get(dst_metric, 0)

        if previous_value != new_value or with_snapshot is True:
            previous[dst_metric] = new[dst_metric] = new_value
    
    def collect_metrics(self, with_snapshot=False):
        logger.debug("BaseHelper.collect_metrics must be overridden")
