# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Celery Signals are disjointed and don't allow us to pass the scope object along
with the Job message so we instead store all scopes in a dictionary on the
registered Task job.

These methods allow pushing and pop'ing of scopes on Task objects.

WeakValueDictionary allows for lost scopes to be garbage collected.
"""
from __future__ import absolute_import

from weakref import WeakValueDictionary


def get_task_id(headers, body):
    """
    Across Celery versions, the task id can exist in a couple of places.
    """
    id = headers.get('id', None)
    if id is None:
        id = body.get('id', None)
    return id


def task_catalog_push(task, task_id, scope, is_consumer):
    """
    Push (adds) an object to the task catalog
    @param task: The Celery Task
    @param task_id:  The Celery Task ID
    @param is_consumer: Boolean
    @return: scope
    """
    catalog = None
    if not hasattr(task, '_instana_scopes'):
        catalog = WeakValueDictionary()
        setattr(task, '_instana_scopes', catalog)
    else:
        catalog = getattr(task, '_instana_scopes')

    key = (task_id, is_consumer)
    catalog[key] = scope


def task_catalog_pop(task, task_id, is_consumer):
    """
    Pop (removes) an object from the task catalog
    @param task: The Celery Task
    @param task_id:  The Celery Task ID
    @param is_consumer: Boolean
    @return: scope
    """
    catalog = getattr(task, '_instana_scopes', None)
    if catalog is None:
        return None

    key = (task_id, is_consumer)
    return catalog.pop(key, None)


def task_catalog_get(task, task_id, is_consumer):
    """
    Get an object from the task catalog
    @param task: The Celery Task
    @param task_id:  The Celery Task ID
    @param is_consumer: Boolean
    @return: scope
    """
    catalog = getattr(task, '_instana_scopes', None)
    if catalog is None:
        return None

    key = (task_id, is_consumer)
    return catalog.get(key, None)

