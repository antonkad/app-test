import os
from flask import Flask, jsonify

app = Flask(__name__)

INTERESTING = (
    "DATABASE", "S3_", "AWS_", "KUBE", "KUBERNETES", "KAD_", "TOKEN",
    "SECRET", "PASSWORD", "POSTGRES", "MINIO", "GARAGE",
)


@app.get("/")
def root():
    keys = sorted(os.environ)
    hits = [k for k in keys if any(p.lower() in k.lower() for p in INTERESTING)]
    return jsonify(
        probe="env-probe",
        key_count=len(keys),
        keys=keys,
        interesting=hits,
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
