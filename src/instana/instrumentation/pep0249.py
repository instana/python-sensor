# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

# This is a wrapper for PEP-0249: Python Database API Specification v2.0
from __future__ import annotations
import wrapt
from typing import TYPE_CHECKING

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from instana.log import logger
from instana.util.traceutils import get_tracer_tuple, tracing_is_off
from instana.util.sql import sql_sanitizer

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


class CursorWrapper(wrapt.ObjectProxy):
    __slots__ = ("_module_name", "_connect_params", "_cursor_params")

    def __init__(
        self, cursor, module_name, connect_params=None, cursor_params=None
    ) -> None:
        super(CursorWrapper, self).__init__(wrapped=cursor)
        self._module_name = module_name
        self._connect_params = connect_params
        self._cursor_params = cursor_params

    def _collect_kvs(self, span, sql) -> InstanaSpan:
        try:
            span.set_attribute(SpanKind, "exit")

            db_parameter_name = next(
                (
                    p
                    for p in ("db", "database", "dbname")
                    if p in self._connect_params[1]
                ),
                None,
            )
            if db_parameter_name:
                span.set_attribute(
                    SpanAttributes.DB_NAME,
                    self._connect_params[1][db_parameter_name],
                )

            span.set_attribute(SpanAttributes.DB_STATEMENT, sql_sanitizer(sql))
            span.set_attribute(SpanAttributes.DB_USER, self._connect_params[1]["user"])
            span.set_attribute("host", self._connect_params[1]["host"])
            span.set_attribute("port", self._connect_params[1]["port"])
        except Exception as e:
            logger.debug(e)
        return span

    def __enter__(self) -> CursorWrapper:
        return self

    def execute(self, sql, params=None) -> None:
        tracer, _, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.execute(sql, params)

        with tracer.start_as_current_span(self._module_name) as span:
            try:
                self._collect_kvs(span, sql)
                result = self.__wrapped__.execute(sql, params)
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
            else:
                return result

    def executemany(self, sql, seq_of_parameters) -> None:
        tracer, _, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.executemany(sql, seq_of_parameters)

        with tracer.start_as_current_span(self._module_name) as span:
            try:
                self._collect_kvs(span, sql)
                result = self.__wrapped__.executemany(sql, seq_of_parameters)
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
            else:
                return result

    def callproc(self, proc_name, params) -> None:
        tracer, _, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.execute(proc_name, params)

        with tracer.start_as_current_span(self._module_name) as span:
            try:
                self._collect_kvs(span, proc_name)
                result = self.__wrapped__.callproc(proc_name, params)
            except Exception:
                try:
                    result = self.__wrapped__.execute(proc_name, params)
                except Exception as e_execute:
                    if span:
                        span.record_exception(e_execute)
                    raise
                else:
                    return result
            else:
                return result


class ConnectionWrapper(wrapt.ObjectProxy):
    __slots__ = ("_module_name", "_connect_params")

    def __init__(self, connection, module_name, connect_params) -> None:
        super(ConnectionWrapper, self).__init__(wrapped=connection)
        self._module_name = module_name
        self._connect_params = connect_params

    def __enter__(self):
        return self

    def cursor(self, *args, **kwargs) -> CursorWrapper:
        return CursorWrapper(
            cursor=self.__wrapped__.cursor(*args, **kwargs),
            module_name=self._module_name,
            connect_params=self._connect_params,
            cursor_params=(args, kwargs) if args or kwargs else None,
        )

    def close(self) -> None:
        return self.__wrapped__.close()

    def commit(self) -> None:
        return self.__wrapped__.commit()

    def rollback(self) -> None:
        return self.__wrapped__.rollback()


class ConnectionFactory(object):
    def __init__(self, connect_func, module_name) -> None:
        self._connect_func = connect_func
        self._module_name = module_name
        self._wrapper_ctor = ConnectionWrapper

    def __call__(self, *args, **kwargs) -> ConnectionWrapper:
        connect_params = (args, kwargs) if args or kwargs else None

        return self._wrapper_ctor(
            connection=self._connect_func(*args, **kwargs),
            module_name=self._module_name,
            connect_params=connect_params,
        )
