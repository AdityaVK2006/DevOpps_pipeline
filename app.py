from flask import Flask, Response, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

app = Flask(__name__)
REQUESTS = Counter("demo_http_requests_total", "HTTP requests handled", ["path"])


@app.get("/")
def home():
    REQUESTS.labels(path="/").inc()
    return jsonify(message="Hello from the DevOps demo", status="running")


@app.get("/health")
def health():
    return jsonify(status="healthy")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
