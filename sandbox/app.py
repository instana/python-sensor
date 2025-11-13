"""
Basic Flask Application for Kubernetes Deployment with Instana
"""

import sys
import os

# Add parent directory to path to import instana from project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import instana  # noqa: F401
from flask import Flask, jsonify
import requests
from multiprocessing import Pool

app = Flask(__name__)


def _make_request(i):
    """Helper function for multiprocessing - must be at module level to be picklable"""
    try:
        response = requests.get("https://www.google.com", timeout=5)
        return {"process": i, "status_code": response.status_code, "success": True}
    except Exception as e:
        return {"process": i, "error": str(e), "success": False}


@app.route("/")
def home():
    """Home endpoint"""
    return jsonify(
        {
            "message": "Hello from Flask in Kubernetes!",
            "status": "running",
            "pod": os.getenv("HOSTNAME", "unknown"),
        }
    )


@app.route("/multiprocess")
def multiprocess():
    """Endpoint that demonstrates multiprocessing with external HTTP requests"""
    num_processes = 5
    with Pool(processes=num_processes) as pool:
        results = pool.map(_make_request, range(num_processes))

    return jsonify(
        {
            "message": "Multiple processes completed",
            "num_processes": num_processes,
            "results": results,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Made with Bob
