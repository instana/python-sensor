from flask import Flask, request, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)


@app.route("/your-endpoint")
def hello_world():
    return "Hello, World from Flask on Kubernetes!"


@app.route("/")
def index():
    return "Flask app is running!"


@app.route("/ibm-multi")
def ibm_multi():
    # how many parallel requests? default 10, configurable via ?n=20
    n = int(request.args.get("n", 10))

    # safety limit so you don't DOS yourself
    n = max(1, min(n, 50))

    def fetch_ibm(i: int):
        resp = requests.get("https://www.ibm.com", timeout=5)
        return {
            "index": i,
            "status_code": resp.status_code,
            "content_length": len(resp.content),
        }

    results = []
    # run them "at the same time" in a thread pool
    with ThreadPoolExecutor(max_workers=n) as executor:
        futures = {executor.submit(fetch_ibm, i): i for i in range(n)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({"index": idx, "error": str(e)})

    return jsonify({"total_requests": n, "results": results})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=3000,
    )
