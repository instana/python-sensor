import logging
import os

from flask import Flask, jsonify, request
from werkzeug.serving import WSGIRequestHandler

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
        for index, span in enumerate(spans):
            if (
                span["n"] == "urllib3"
                and span["data"]["http"]["url"]
                == "http://localhost:42699/com.instana.agent.logger"
            ):
                continue
            print(f"- {index}. Span")
            print(
                f"Name: {span['n']} {span['data']['kafka']['access'] if span['n'] == 'kafka' else ''}"
            )
            print(f"Trace ID: {span['t']}")
            print(f"Span ID: {span['s']}")
            print(f"Timestamp: {span['ts']})")
    return jsonify({"spans": spans}), 200


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 42699))
    app.run(
        debug=True,
        host=host,
        port=port,
        use_reloader=False,
        request_handler=QuietRequestHandler,
    )
