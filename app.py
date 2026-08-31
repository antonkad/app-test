import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

from flask import Flask, jsonify

app = Flask(__name__)


def tcp_check(host, port, timeout=2.0):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return "open"
    except socket.timeout:
        return "timeout"
    except OSError as e:
        return f"error:{type(e).__name__}"
    except Exception as e:
        return f"error:{type(e).__name__}"


def https_get_noauth(url, timeout=5.0):
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return {"status": resp.status}
    except urllib.error.HTTPError as e:
        return {"status": e.code}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}


def load_build_probe():
    try:
        with open("/build-probe.json") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


@app.get("/")
def root():
    build = load_build_probe()
    runtime_tcp = tcp_check("192.168.1.150", 5432)
    return jsonify(
        ok=True,
        app="app-test",
        branch="build-probe",
        build_probe=build,
        runtime_tcp_192_168_1_150_5432=runtime_tcp,
        runtime_unauth_kube_api=https_get_noauth("https://kubernetes.default.svc/api"),
        runtime_ts=int(time.time()),
    )


@app.get("/build-probe.json")
def build_probe_raw():
    build = load_build_probe()
    if build is None:
        return jsonify(error="build probe not found"), 404
    return jsonify(build)


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))