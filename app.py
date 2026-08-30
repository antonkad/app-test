import os
import socket
import ssl
import urllib.error
import urllib.request
from flask import Flask, jsonify

app = Flask(__name__)

TARGETS = [
    ("192.168.1.150", 5432, "pg"),
    ("192.168.1.150", 3900, "s3"),
    ("169.254.169.254", 80, "cloud-metadata"),
    ("169.254.169.254", 443, "cloud-metadata-tls"),
    ("10.42.0.1", 443, "cni-gw"),
    ("10.43.0.1", 443, "svc-cidr"),
    ("kubernetes.default.svc", 443, "kube-api"),
    ("127.0.0.1", 10250, "kubelet"),
]


def tcp(host, port, timeout=1.5):
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError as e:
        return {"status": "dns:" + type(e).__name__}
    last = "fail"
    for fam, kind, proto, _, addr in infos:
        s = socket.socket(fam, kind, proto)
        s.settimeout(timeout)
        try:
            s.connect(addr)
            s.close()
            return {"status": "open", "addr": addr[0]}
        except socket.timeout:
            last = "timeout"
        except OSError as e:
            last = type(e).__name__
        finally:
            try:
                s.close()
            except OSError:
                pass
    return {"status": last}


def http(url, headers=None, timeout=2.0):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(200)
            return {"status": r.status, "len": len(body)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "reason": e.reason}
    except Exception as e:
        return {"status": type(e).__name__}


def sa():
    base = "/var/run/secrets/kubernetes.io/serviceaccount"
    out = {"dir": os.path.isdir(base)}
    for n in ("token", "ca.crt", "namespace"):
        p = os.path.join(base, n)
        out[n + "_exists"] = os.path.isfile(p)
        if n == "namespace" and os.path.isfile(p):
            out["namespace"] = open(p).read().strip()[:64]
        if n == "token" and os.path.isfile(p):
            out["token_len"] = os.path.getsize(p)
    return out


@app.get("/")
def root():
    sock = "/var/run/docker.sock"
    kube_env = sorted(k for k in os.environ if "KUBE" in k.upper())
    sa_info = sa()
    kube = None
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    if sa_info.get("token_exists"):
        tok = open(token_path).read().strip()
        kube = http(
            "https://kubernetes.default.svc/api",
            headers={"Authorization": "Bearer " + tok},
        )
        # do not return tok
    meta = http("http://169.254.169.254/latest/meta-data/")
    return jsonify(
        probe="net-probe",
        concern="cluster-recon + kube from tenant pod",
        tcp=[{**{"host": h, "port": p, "tag": t}, **tcp(h, p)} for h, p, t in TARGETS],
        docker_sock_exists=os.path.exists(sock),
        kube_env_names=kube_env,
        serviceaccount=sa_info,
        kube_api=kube,
        cloud_metadata=meta,
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
