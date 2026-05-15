# (C) Copyright IBM Corp. 2026

"""
Instana Werkzeug Instrumentation

This module provides automatic instrumentation for Werkzeug-based applications.
Werkzeug is a comprehensive WSGI web application library used by Flask and other frameworks.

This module automatically patches Werkzeug applications when imported via wrapt.
"""

try:
    from typing import Any, Callable

    import wrapt

    from instana.instrumentation.wsgi import InstanaWSGIMiddleware
    from instana.log import logger

    def _is_flask_app(app: Any) -> bool:
        """
        Check if the application is a Flask app.

        Flask apps have their own instrumentation, so we skip wrapping them
        to avoid double instrumentation (2 spans per request).

        Args:
            app: The WSGI application to check

        Returns:
            True if app is a Flask application, False otherwise
        """
        try:
            # Check if it's a Flask app by class name
            if hasattr(app, "__class__"):
                class_name = app.__class__.__name__
                module_name = getattr(app.__class__, "__module__", "")

                # Direct Flask app check
                if class_name == "Flask" and "flask" in module_name:
                    return True

                # Check for Flask app wrapped in middleware
                if hasattr(app, "wsgi_app"):
                    return _is_flask_app(app.wsgi_app)

            return False
        except Exception:
            logger.debug("Error checking if app is Flask", exc_info=True)
            return False

    @wrapt.patch_function_wrapper("werkzeug.serving", "run_simple")
    def run_simple_with_instana(
        wrapped: Callable,
        instance: Any,
        args: tuple,
        kwargs: dict[str, Any],
    ) -> Any:
        """
        Patch werkzeug.serving.run_simple to wrap WSGI applications.

        Skips Flask applications as they have their own instrumentation.
        """
        try:
            # run_simple(hostname, port, application, ...)
            if len(args) >= 3:
                hostname, port, application = args[0], args[1], args[2]

                # Skip Flask apps (they have their own instrumentation)
                if _is_flask_app(application):
                    logger.debug(
                        f"Skipping Werkzeug instrumentation for Flask app at {hostname}:{port}"
                    )
                    return wrapped(*args, **kwargs)

                # Wrap non-Flask WSGI apps
                instrumented_app = InstanaWSGIMiddleware(
                    application, status_as_string=False
                )
                logger.debug(f"Werkzeug app wrapped: {hostname}:{port}")
                args = (hostname, port, instrumented_app) + args[3:]
            elif "application" in kwargs:
                application = kwargs["application"]

                # Skip Flask apps (they have their own instrumentation)
                if _is_flask_app(application):
                    logger.debug(
                        "Skipping Werkzeug instrumentation for Flask app (kwargs)"
                    )
                    return wrapped(*args, **kwargs)

                # Wrap non-Flask WSGI apps
                instrumented_app = InstanaWSGIMiddleware(
                    application, status_as_string=False
                )
                kwargs["application"] = instrumented_app
                logger.debug("Werkzeug app wrapped (kwargs)")
        except Exception:
            logger.debug("Failed to wrap Werkzeug app", exc_info=True)

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting werkzeug")

except ImportError:
    pass

# Made with Bob
