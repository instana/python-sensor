from flask import Flask

app = Flask(__name__)


@app.route("/your-endpoint")
def hello_world():
    return "Hello, World from Flask on Kubernetes!"


@app.route("/")
def index():
    return "Flask app is running!"


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=3000,
    )
