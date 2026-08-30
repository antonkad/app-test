import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def root():
    keys = {
        "S3_ENDPOINT": os.environ.get("S3_ENDPOINT"),
        "S3_BUCKET": os.environ.get("S3_BUCKET"),
        "S3_REGION": os.environ.get("S3_REGION"),
        "S3_FORCE_PATH_STYLE": os.environ.get("S3_FORCE_PATH_STYLE"),
        "has_access_key": "S3_ACCESS_KEY" in os.environ,
        "has_secret_key": "S3_SECRET_KEY" in os.environ,
    }
    listed = None
    err = None
    if keys["S3_ENDPOINT"] and keys["has_access_key"]:
        try:
            import boto3
            from botocore.config import Config

            c = boto3.client(
                "s3",
                endpoint_url=keys["S3_ENDPOINT"],
                aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
                aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
                region_name=keys["S3_REGION"] or "us-east-1",
                config=Config(s3={"addressing_style": "path"}),
            )
            buckets = [b["Name"] for b in c.list_buckets().get("Buckets", [])]
            ours = keys["S3_BUCKET"]
            listed = {
                "bucket_count": len(buckets),
                "this_bucket": ours,
                "other_buckets": [b for b in buckets if b != ours],
            }
        except Exception as e:
            err = type(e).__name__ + ": " + str(e)[:200]
    return jsonify(probe="s3-probe", env=keys, list_buckets=listed, error=err)


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
