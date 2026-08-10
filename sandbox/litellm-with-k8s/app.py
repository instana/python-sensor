#!/usr/bin/env python3
# (c) Copyright IBM Corp. 2025
"""
LiteLLM proxy application — automatically instrumented by the Instana autotrace webhook.
No manual import is needed; the webhook injects the sensor via PYTHONPATH.

Endpoints:
  GET  /health            — liveness / readiness probe
  GET  /models            — configured model list
  POST /chat/completions  — OpenAI-compatible chat endpoint (proxied to fake-openai)
  POST /completions       — OpenAI-compatible completions endpoint
  GET  /slow              — 1-second delay for trace duration testing
"""

import os
import time

import litellm
from flask import Flask, jsonify, request

app = Flask(__name__)

# ── LiteLLM configuration ─────────────────────────────────────────────────────
# FAKE_OPENAI_URL is passed as an env var; default: in-cluster service name
FAKE_OPENAI_BASE = os.environ.get("FAKE_OPENAI_URL", "http://fake-openai:8080")

litellm.set_verbose = os.environ.get("LITELLM_VERBOSE", "false").lower() == "true"


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "pid": os.getpid()})


# ── Model list ────────────────────────────────────────────────────────────────
@app.route("/models")
def models():
    return jsonify({
        "object": "list",
        "data": [
            {"id": "fake-gpt-4", "object": "model", "owned_by": "fake-openai"},
        ],
    })


# ── Chat completions ──────────────────────────────────────────────────────────
@app.route("/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json(force=True)
    messages = body.get("messages", [{"role": "user", "content": "hello"}])
    model = body.get("model", "fake-gpt-4")

    response = litellm.completion(
        model=f"openai/{model}",
        messages=messages,
        api_base=FAKE_OPENAI_BASE,
        api_key="fake-key",
    )
    return jsonify(response.model_dump())


# ── Completions (legacy) ──────────────────────────────────────────────────────
@app.route("/completions", methods=["POST"])
def completions():
    body = request.get_json(force=True)
    prompt = body.get("prompt", "Say hello")
    model = body.get("model", "fake-gpt-4")

    response = litellm.completion(
        model=f"openai/{model}",
        messages=[{"role": "user", "content": prompt}],
        api_base=FAKE_OPENAI_BASE,
        api_key="fake-key",
    )
    return jsonify(response.model_dump())


# ── Slow endpoint (1-second delay for trace duration testing) ─────────────────
@app.route("/slow")
def slow():
    time.sleep(1)
    return jsonify({"message": "This took 1 second", "pid": os.getpid()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
