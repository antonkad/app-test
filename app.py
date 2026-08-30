import os
import socket
from flask import Flask, jsonify

app = Flask(__name__)

TARGETS = [
    ("192.168.1.150", 5432, "pg"),
    ("192.168.1.150", 3900, "s3"),
    ("169.254.169.254", 80, "metadata"),
    ("10.42.0.1", 443, "cni"),
    ("kubernetes.default.svc", 443, "kube"),
]


def probe(host, port, timeout=1.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return "open"
    except socket.timeout:
        return "timeout"
    except OSError as e:
        return type(e).__name__
    finally:
        try:
            s.close()
        except OSError:
            pass


@app.get("/")
def root():
    return jsonify(
        probe="net-probe",
        results=[
            {"host": h, "port": p, "tag": t, "status": probe(h, p)}
            for h, p, t in TARGETS
        ],
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
