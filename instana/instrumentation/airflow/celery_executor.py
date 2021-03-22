#  (c) Copyright IBM Corp. 2021
#  (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import opentracing

import wrapt

from ...log import logger
from ...singletons import tracer

try:
    import airflow.executors.celery_executor
    import celery

    @wrapt.patch_function_wrapper("airflow.executors.celery_executor", "CeleryExecutor.queue_command")
    def execute_command_with_instana(wrapped, instance, args, kwargs):
        task_instance, *_ = args

        with tracer.start_active_span("airflow-task", child_of=tracer.active_span) as scope:
            scope.span.set_tag("op", "queue")
            scope.span.set_tag("dag_id", task_instance.dag_id)
            scope.span.set_tag("task_id", task_instance.task_id)
            scope.span.set_tag("exec_date", task_instance.execution_date)

            # Add the current span context to the TaskInstance to pick it up in Task.apply_async later
            task_instance.__instana_span_context = scope.span.context

            return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("airflow.executors.celery_executor", "CeleryExecutor._send_tasks_to_celery")
    def send_send_tasks_to_celery_with_instana(wrapped, instance, args, kwargs):
        try:
            for (_, task_instance, _, _, task_to_run) in args[0]:
                if hasattr(task_instance, "__instana_span_context"):
                    # forward the Airflow span context to the celery Task instance
                    task_to_run.__instana_airflow_task = {
                        "context": task_instance.__instana_span_context,
                        "dag_id": task_instance.dag_id,
                        "task_id": task_instance.task_id,
                        "execution_date": task_instance.execution_date
                    }
        except Exception:
            logger.debug("Instana: airflow.send_send_tasks_to_celery_with_instana error", exc_info=True)
        finally:
            return wrapped(*args, **kwargs)

    @wrapt.patch_function_wrapper("celery", "Task.apply_async")
    def apply_async_with_instana(wrapped, instance, args, kwargs):
        if not hasattr(instance, '__instana_airflow_task'):
            return wrapped(*args, **kwargs)

        task_metadata = instance.__instana_airflow_task
        with tracer.start_active_span("airflow-task", child_of=task_metadata["context"]) as scope:
            scope.span.set_tag("op", "execute")
            scope.span.set_tag("dag_id", task_metadata["dag_id"])
            scope.span.set_tag("task_id", task_metadata["task_id"])
            scope.span.set_tag("exec_date", task_metadata["execution_date"])

            try:
                return wrapped(*args, **kwargs)
            except Exception as e:
                span.log_exception(e)
                raise
            else:
                return res

    logger.debug("Instrumenting Airflow celery executor")
except ImportError:
    pass
