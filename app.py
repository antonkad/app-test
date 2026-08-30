import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def root():
    return jsonify(
        ok=True,
        app="app-test",
        framework="flask",
        port=os.environ.get("PORT", "8080"),
        has_database_url="DATABASE_URL" in os.environ,
        has_s3="S3_ENDPOINT" in os.environ,
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
