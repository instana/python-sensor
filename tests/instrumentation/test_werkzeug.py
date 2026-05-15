# (C) Copyright IBM Corp. 2026

"""
Tests for Werkzeug instrumentation.

Verifies that Flask apps are skipped to avoid double instrumentation.
"""

import unittest
from unittest.mock import Mock, patch

from instana.instrumentation.werkzeug import _is_flask_app
from instana.instrumentation.wsgi import InstanaWSGIMiddleware


class TestWerkzeugInstrumentation(unittest.TestCase):
    """Test Werkzeug instrumentation behavior."""

    def test_is_flask_app_detects_flask(self):
        """Test that _is_flask_app correctly identifies Flask apps."""
        # Create a mock Flask app
        mock_flask_app = Mock()
        mock_flask_app.__class__.__name__ = "Flask"
        mock_flask_app.__class__.__module__ = "flask.app"

        self.assertTrue(_is_flask_app(mock_flask_app))

    def test_is_flask_app_detects_wrapped_flask(self):
        """Test that _is_flask_app detects Flask apps wrapped in middleware."""
        # Create a mock Flask app
        mock_flask_app = Mock()
        mock_flask_app.__class__.__name__ = "Flask"
        mock_flask_app.__class__.__module__ = "flask.app"

        # Wrap it in middleware
        mock_wrapper = Mock()
        mock_wrapper.__class__.__name__ = "DispatcherMiddleware"
        mock_wrapper.wsgi_app = mock_flask_app

        self.assertTrue(_is_flask_app(mock_wrapper))

    def test_is_flask_app_rejects_non_flask(self):
        """Test that _is_flask_app rejects non-Flask WSGI apps."""
        # Create a mock non-Flask WSGI app
        mock_wsgi_app = Mock()
        mock_wsgi_app.__class__.__name__ = "Application"
        mock_wsgi_app.__class__.__module__ = "myapp"

        self.assertFalse(_is_flask_app(mock_wsgi_app))

    def test_is_flask_app_handles_none(self):
        """Test that _is_flask_app handles None gracefully."""
        self.assertFalse(_is_flask_app(None))

    def test_is_flask_app_handles_callable(self):
        """Test that _is_flask_app handles plain callables."""

        def simple_wsgi_app(environ, start_response):
            return []

        self.assertFalse(_is_flask_app(simple_wsgi_app))

    @patch("instana.instrumentation.werkzeug.logger")
    def test_is_flask_app_handles_exceptions(self, mock_logger):
        """Test that _is_flask_app handles exceptions gracefully."""

        # Create an object that raises on attribute access
        class BrokenApp:
            @property
            def __class__(self):
                raise RuntimeError("Broken!")

        broken_app = BrokenApp()
        result = _is_flask_app(broken_app)

        self.assertFalse(result)
        mock_logger.debug.assert_called_once()


class TestWerkzeugFlaskIntegration(unittest.TestCase):
    """Test Werkzeug instrumentation logic with Flask apps."""

    def test_flask_app_detection_in_args(self):
        """Test that Flask apps in args are detected and not wrapped."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock Flask app
        mock_flask_app = Mock()
        mock_flask_app.__class__.__name__ = "Flask"
        mock_flask_app.__class__.__module__ = "flask.app"

        # Verify Flask detection works
        self.assertTrue(_is_flask_app(mock_flask_app))

    def test_non_flask_app_detection(self):
        """Test that non-Flask WSGI apps are correctly identified."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock non-Flask WSGI app
        mock_wsgi_app = Mock()
        mock_wsgi_app.__class__.__name__ = "Application"
        mock_wsgi_app.__class__.__module__ = "myapp"

        # Verify non-Flask detection works
        self.assertFalse(_is_flask_app(mock_wsgi_app))

    @patch("instana.instrumentation.werkzeug.logger")
    def test_wrapping_logic_skips_flask(self, mock_logger):
        """Test the wrapping logic skips Flask apps."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock Flask app
        mock_flask_app = Mock()
        mock_flask_app.__class__.__name__ = "Flask"
        mock_flask_app.__class__.__module__ = "flask.app"

        # Simulate the logic in run_simple_with_instana
        if _is_flask_app(mock_flask_app):
            # Should skip wrapping
            wrapped_app = mock_flask_app
        else:
            # Should wrap
            wrapped_app = InstanaWSGIMiddleware(mock_flask_app)

        # Verify Flask app was NOT wrapped
        self.assertIs(wrapped_app, mock_flask_app)
        self.assertNotIsInstance(wrapped_app, InstanaWSGIMiddleware)

    @patch("instana.instrumentation.werkzeug.logger")
    def test_wrapping_logic_wraps_non_flask(self, mock_logger):
        """Test the wrapping logic wraps non-Flask apps."""
        from instana.instrumentation.werkzeug import _is_flask_app

        # Mock non-Flask WSGI app
        mock_wsgi_app = Mock()
        mock_wsgi_app.__class__.__name__ = "Application"
        mock_wsgi_app.__class__.__module__ = "myapp"

        # Simulate the logic in run_simple_with_instana
        if _is_flask_app(mock_wsgi_app):
            # Should skip wrapping
            wrapped_app = mock_wsgi_app
        else:
            # Should wrap
            wrapped_app = InstanaWSGIMiddleware(mock_wsgi_app)

        # Verify non-Flask app WAS wrapped
        self.assertIsNot(wrapped_app, mock_wsgi_app)
        self.assertIsInstance(wrapped_app, InstanaWSGIMiddleware)


if __name__ == "__main__":
    unittest.main()

# Made with Bob
