#!/usr/bin/env python3
"""
Simple Flask application instrumented with Instana for IPv6 testing.
"""

import os
import time

# Configure Instana agent connection BEFORE importing instana
AGENT_HOST = os.getenv("INSTANA_AGENT_HOST", "127.0.0.1")
AGENT_PORT = os.getenv("INSTANA_AGENT_PORT", "42699")

os.environ["INSTANA_AGENT_HOST"] = AGENT_HOST
os.environ["INSTANA_AGENT_PORT"] = AGENT_PORT

# Import instana AFTER setting environment variables
import instana
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    """Home endpoint"""
    return jsonify({
        "message": "Hello from Instana IPv6 Test App!",
        "agent": f"{AGENT_HOST}:{AGENT_PORT}",
    })


@app.route("/hello/<name>")
def hello(name):
    """Personalized greeting"""
    return jsonify({"message": f"Hello, {name}!", "timestamp": time.time()})


@app.route("/slow")
def slow():
    """Slow endpoint"""
    time.sleep(1)
    return jsonify({"message": "This took 1 second"})


@app.route("/error")
def error():
    """Error endpoint"""
    raise Exception("Test error for Instana tracing")


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 5001))

    print("=" * 60)
    print("Simple Flask App with Instana")
    print("=" * 60)
    print(f"App: http://{host}:{port}")
    print(f"Instana Agent: {AGENT_HOST}:{AGENT_PORT}")
    print("=" * 60)

    app.run(host=host, port=port, debug=True, use_reloader=False)

# Made with Bob
