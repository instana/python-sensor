#!/usr/bin/env python3
# (c) Copyright IBM Corp. 2025
"""
Simple Flask application instrumented with Instana via AUTOWRAPT_BOOTSTRAP.

Instrumentation is injected at Python startup via autowrapt — no explicit
"import instana" is needed in application code.  Set the following env vars
before running:

  AUTOWRAPT_BOOTSTRAP=instana
  INSTANA_AGENT_HOST=<agent-host>   (default: localhost)
  INSTANA_AGENT_PORT=42699
"""

import os
import time

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    """Root endpoint — always returns 200."""
    return jsonify({
        "message": "Hello from Instana Flask tracing demo!",
        "service": os.getenv("INSTANA_SERVICE_NAME", "flask-tracing-demo"),
    })


@app.route("/hello/<name>")
def hello(name: str):
    """Personalised greeting that generates a named entry span."""
    return jsonify({"message": f"Hello, {name}!", "timestamp": time.time()})


@app.route("/slow")
def slow():
    """Endpoint that sleeps 1 s — useful for latency visibility in Instana UI."""
    time.sleep(1)
    return jsonify({"message": "Completed after 1 second"})


@app.route("/error")
def error():
    """Deliberately raises an exception so Instana records an error span."""
    raise ValueError("Intentional test error for Instana tracing")


@app.route("/healthz")
def healthz():
    """Kubernetes liveness / readiness probe endpoint (not traced)."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "5000"))

    print("=" * 60)
    print("Flask Instana Tracing Demo")
    print("=" * 60)
    print(f"Listening on  : http://{host}:{port}")
    print(f"Agent host    : {os.getenv('INSTANA_AGENT_HOST', 'localhost')}:{os.getenv('INSTANA_AGENT_PORT', '42699')}")
    print(f"Autowrapt     : {os.getenv('AUTOWRAPT_BOOTSTRAP', 'NOT SET — instrumentation disabled')}")
    print("=" * 60)

    app.run(host=host, port=port, debug=False, use_reloader=False)
