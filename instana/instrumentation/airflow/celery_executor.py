# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import opentracing

import wrapt

from ...log import logger
from ...singletons import tracer, get_agent

import logging
LOGGER = logging.getLogger("INSTANA")
LOGGER.setLevel(logging.DEBUG)

import os
import time

try:
    import airflow.executors.celery_executor
    import celery

    agent = get_agent()

    class _CommandWithTraceContext:
        def __init__(self, cmd, ctx, dag_id, task_id, execution_date):
            self.command = cmd
            self.context = ctx
            self.dag_id = dag_id
            self.task_id = task_id
            self.execution_date = execution_date

        def __str__(self):
            return self.command.__str__()

        def __repr__(self):
            return self.command.__repr__()

    def __bind_queue_command_args(task_instance, command, *args):
        return task_instance, command, args

    @wrapt.patch_function_wrapper("airflow.executors.celery_executor", "CeleryExecutor.queue_command")
    def _queue_command_with_instana(wrapped, instance, args, kwargs):
        task_instance, command, args = __bind_queue_command_args(*args)

        LOGGER.info(">>>>> Scheduling {}.{}, pid: {}".format(task_instance.dag_id, task_instance.task_id, os.getpid()))

        with tracer.start_active_span("airflow-task") as scope:
            scope.span.set_tag("op", "ENQUEUE")
            scope.span.set_tag("dag_id", task_instance.dag_id)
            scope.span.set_tag("task_id", task_instance.task_id)
            scope.span.set_tag("exec_date", task_instance.execution_date)

            # Wrap command to provide the task instance data and trace context to the Task.apply_async
            command = _CommandWithTraceContext(command,
                                               scope.span.context,
                                               task_instance.dag_id,
                                               task_instance.task_id,
                                               task_instance.execution_date)

            args = (task_instance, command) + args

            return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("celery", "Task.apply_async")
    def _apply_async_with_instana(wrapped, instance, args, kwargs):
        cmd = kwargs["args"][0]

        if not isinstance(cmd, _CommandWithTraceContext):
            LOGGER.warn(">>>>> The command came unwrapped {}".format(cmd))
            return wrapped(*args, **kwargs)

        LOGGER.info(">>>>> Executing {}.{}, pid: {}".format(cmd.dag_id, cmd.task_id, os.getpid()))

        # Restore the original command list
        kwargs["args"] = [cmd.command]

        with tracer.start_active_span("airflow-task", child_of=cmd.context) as scope:
            scope.span.set_tag("op", "EXECUTE")
            scope.span.set_tag("dag_id", cmd.dag_id)
            scope.span.set_tag("task_id", cmd.task_id)
            scope.span.set_tag("exec_date", cmd.execution_date)

            try:
                res = wrapped(*args, **kwargs)
                LOGGER.info(">>>>> {}.{} has been executed".format(cmd.dag_id, cmd.task_id))
            except Exception as e:
                LOGGER.error(">>>>> Failed to execute {}.{}".format(cmd.dag_id, cmd.task_id), exc_info=True)
                scope.span.log_exception(e)
                raise
            else:
                return res

    @wrapt.patch_function_wrapper("airflow.executors.celery_executor", "CeleryExecutor.end")
    def _CeleryExecutor_end_with_instana(wrapped, instance, args, kwargs):
        agent.collector.shutdown()
        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting Airflow celery executor")
except ImportError:
    pass
