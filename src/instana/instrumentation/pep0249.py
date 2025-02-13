# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

# This is a wrapper for PEP-0249: Python Database API Specification v2.0
import wrapt
from typing import TYPE_CHECKING, Dict, Any, List, Tuple, Union, Callable, Optional
from typing_extensions import Self

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
        self,
        cursor: Any,
        module_name: str,
        connect_params: Optional[List[Union[str, Dict[str, Any]]]] = None,
        cursor_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super(CursorWrapper, self).__init__(wrapped=cursor)
        self._module_name = module_name
        self._connect_params = connect_params
        self._cursor_params = cursor_params

    def _collect_kvs(
        self,
        span: "InstanaSpan",
        sql: str,
    ) -> None:
        try:
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

    def __enter__(self) -> Self:
        return self

    def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Callable[[str, Dict[str, Any]], None]:
        tracer, parent_span, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.execute(sql, params)

        parent_context = parent_span.get_span_context() if parent_span else None
        with tracer.start_as_current_span(
            self._module_name, span_context=parent_context
        ) as span:
            try:
                self._collect_kvs(span, sql)
                result = self.__wrapped__.execute(sql, params)
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
            else:
                return result

    def executemany(
        self,
        sql: str,
        seq_of_parameters: List[Dict[str, Any]],
    ) -> Callable[[str, List[Dict[str, Any]]], None]:
        tracer, parent_span, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.executemany(sql, seq_of_parameters)

        parent_context = parent_span.get_span_context() if parent_span else None
        with tracer.start_as_current_span(
            self._module_name, span_context=parent_context
        ) as span:
            try:
                self._collect_kvs(span, sql)
                result = self.__wrapped__.executemany(sql, seq_of_parameters)
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
            else:
                return result

    def callproc(
        self,
        proc_name: str,
        params: Dict[str, Any],
    ) -> Callable[[str, Dict[str, Any]], None]:
        tracer, parent_span, operation_name = get_tracer_tuple()

        # If not tracing or we're being called from sqlalchemy, just pass through
        if tracing_is_off() or (operation_name == "sqlalchemy"):
            return self.__wrapped__.execute(proc_name, params)

        parent_context = parent_span.get_span_context() if parent_span else None
        with tracer.start_as_current_span(
            self._module_name, span_context=parent_context
        ) as span:
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

    def __init__(
        self,
        connection: "ConnectionWrapper",
        module_name: str,
        connect_params: List[Union[str, Dict[str, Any]]],
    ) -> None:
        super(ConnectionWrapper, self).__init__(wrapped=connection)
        self._module_name = module_name
        self._connect_params = connect_params

    def __enter__(self) -> Self:
        return self

    def cursor(
        self,
        *args: Tuple[int, str, Dict[str, Any]],
        **kwargs: Dict[str, Any],
    ) -> CursorWrapper:
        return CursorWrapper(
            cursor=self.__wrapped__.cursor(*args, **kwargs),
            module_name=self._module_name,
            connect_params=self._connect_params,
            cursor_params=(args, kwargs) if args or kwargs else None,
        )

    def close(self) -> Callable[[], None]:
        return self.__wrapped__.close()

    def commit(self) -> Callable[[], None]:
        return self.__wrapped__.commit()

    def rollback(self) -> Callable[[], None]:
        return self.__wrapped__.rollback()


class ConnectionFactory(object):
    def __init__(
        self,
        connect_func: CursorWrapper,
        module_name: str,
    ) -> None:
        self._connect_func = connect_func
        self._module_name = module_name
        self._wrapper_ctor = ConnectionWrapper

    def __call__(
        self,
        *args: Tuple[int, str, Dict[str, Any]],
        **kwargs: Dict[str, Any],
    ) -> ConnectionWrapper:
        connect_params = (args, kwargs) if args or kwargs else None
        return self._wrapper_ctor(
            connection=self._connect_func(*args, **kwargs),
            module_name=self._module_name,
            connect_params=connect_params,
        )
