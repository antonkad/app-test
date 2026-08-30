import os
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/")
def root():
    names = sorted(request.cookies.keys())
    raw = request.headers.get("Cookie")
    return jsonify(
        probe="cookie-trap",
        cookie_header_present=raw is not None,
        cookie_names=names,
        cookie_count=len(names),
        has_kad_token="kad_token" in request.cookies,
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
