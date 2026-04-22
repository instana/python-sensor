import logging
import os
import requests
from threading import Thread

from flask import Flask, jsonify, request
from werkzeug.serving import WSGIRequestHandler

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# IPv6 support configuration
USE_IPV6 = os.getenv("USE_IPV6", "false").lower() in ("true", "1", "yes")

# Get span listener port from environment
SPAN_LISTENER_PORT = int(os.getenv("SPAN_LISTENER_PORT", 42700))


# Helper functions for IPv6 support
def is_ipv6_address(host):
    """Check if a host string is an IPv6 address"""
    # IPv6 addresses contain colons but not :// (URL scheme)
    return ":" in host and "://" not in host and not host.startswith("[")


def format_host_for_url(host):
    """Format host for URL, adding brackets for IPv6 addresses"""
    if is_ipv6_address(host):
        return f"[{host}]"
    return host


# Construct span listener URL with proper IPv6 support
SPAN_LISTENER_HOST = "::1" if USE_IPV6 else "127.0.0.1"
SPAN_LISTENER_URL = (
    f"http://{format_host_for_url(SPAN_LISTENER_HOST)}:{SPAN_LISTENER_PORT}/spans"
)


def send_spans_to_extension(spans):
    """Send spans to the VS Code extension in a background thread"""

    def _send():
        try:
            requests.post(SPAN_LISTENER_URL, json=spans, timeout=1)
        except Exception as e:
            # Silently fail if extension is not listening
            logger.debug(f"Failed to send spans to extension: {e}")

    Thread(target=_send, daemon=True).start()


class QuietRequestHandler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        # Suppress logs for specific endpoint
        if self.path.startswith("/com.instana"):
            return  # Don't log this
        # Otherwise, default behavior
        super().log_request(code, size)


# response: b'{"pid":31003,"agentUuid":"00:e6:02:ff:fe:01:9f:cc","secrets":{"matcher":"contains-ignore-case","list":["key","pass","secret"]}}'
@app.route("/")
def home():
    response = {
        "pid": os.getpid(),
        "agentUuid": "00:e6:02:ff:fe:01:9f:cc",
        "secrets": {
            "matcher": "contains-ignore-case",
            "list": ["key", "pass", "secret"],
        },
    }
    return jsonify(response), 200


# response: b'{"pid":31003,"agentUuid":"00:e6:02:ff:fe:01:9f:cc","secrets":{"matcher":"contains-ignore-case","list":["key","pass","secret"]}}'
@app.route("/com.instana.plugin.python.discovery", methods=["PUT"])
def discovery():
    response = {
        "pid": os.getpid(),
        "agentUuid": "00:e6:02:ff:fe:01:9f:cc",
        "secrets": {
            "matcher": "contains-ignore-case",
            "list": ["key", "pass", "secret"],
        },
    }
    return jsonify(response), 200


# response: b'[]'
@app.route("/com.instana.plugin.python.<int:pid>", methods=["HEAD", "POST"])
def is_agent_ready(pid):
    return "[]", 200


# response: b''
@app.route("/com.instana.agent.logger", methods=["POST"])
def agent_logger():
    return "", 200


# response: b''
@app.route("/com.instana.plugin.python/traces.<int:pid>", methods=["POST"])
def traces(pid):
    spans = request.get_json(silent=True)
    if spans:
        # Filter out internal spans and send to extension
        filtered_spans = []
        for span in spans:
            # Get the URL from the span
            url = span.get("data", {}).get("http", {}).get("url", "")

            # Filter out internal agent logger calls (both IPv4 and IPv6)
            if span.get("n") == "urllib3" and (
                url.startswith("http://localhost:42699/com.instana.agent.logger")
                or url.startswith("http://127.0.0.1:42699/com.instana.agent.logger")
                or url.startswith("http://[::1]:42699/com.instana.agent.logger")
            ):
                continue
            filtered_spans.append(span)

        # Send filtered spans to VS Code extension
        if filtered_spans:
            send_spans_to_extension(filtered_spans)
            logger.info(f"Received {len(filtered_spans)} span(s)")

    return jsonify({"spans": spans}), 200


if __name__ == "__main__":
    # Determine host binding based on IPv6 configuration
    # :: binds to all interfaces (IPv4 and IPv6) when IPv6 is enabled
    # 0.0.0.0 binds to all IPv4 interfaces
    default_host = "::" if USE_IPV6 else "0.0.0.0"
    host = os.getenv("HOST", default_host)
    port = int(os.getenv("PORT", 42699))

    # Log startup information
    logger.info("=" * 60)
    logger.info("Fake Instana Agent Starting")
    logger.info(f"IPv6 Mode: {'ENABLED' if USE_IPV6 else 'DISABLED'}")
    logger.info(f"Listening on: {format_host_for_url(host)}:{port}")
    logger.info(f"Span Listener URL: {SPAN_LISTENER_URL}")
    logger.info("=" * 60)

    app.run(
        debug=True,
        host=host,
        port=port,
        use_reloader=False,
        request_handler=QuietRequestHandler,
    )

# Made with Bob
