import json
import os
import re
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
    ("192.168.1.150", 10250, "kubelet-lan"),
    ("10.42.0.1", 10250, "kubelet-cni"),
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


def kubelet_healthz(host, timeout=2.0):
    url = "https://%s:10250/healthz" % host
    req = urllib.request.Request(url, method="GET")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(64)
            return {"status": r.status, "body_head": body.decode("utf-8", "replace")}
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


def kube_get(path, token):
    req = urllib.request.Request(
        "https://kubernetes.default.svc" + path,
        headers={"Authorization": "Bearer " + token},
        method="GET",
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=5.0, context=ctx) as r:
            body = r.read()
            return {"status": r.status, "body": body.decode("utf-8", "replace")[:65536]}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", "replace")[:2048]}
    except Exception as e:
        return {"status": type(e).__name__, "body": None}


def dns(name):
    try:
        infos = socket.getaddrinfo(name, None)
    except OSError as e:
        return {"name": name, "resolved": False, "err": type(e).__name__}
    addrs = sorted({info[4][0] for info in infos})
    return {"name": name, "resolved": True, "addrs": addrs}


def listening_count(path):
    try:
        with open(path) as f:
            lines = f.read().splitlines()[1:]
    except OSError as e:
        return {"path": path, "count": -1, "err": type(e).__name__}
    count = sum(1 for ln in lines if len(ln.split()) >= 4 and ln.split()[3] == "0A")
    return {"path": path, "count": count}


def kube_unauth_api():
    req = urllib.request.Request("https://kubernetes.default.svc/api", method="GET")
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=5.0, context=ctx) as r:
            return {"status": r.status}
    except urllib.error.HTTPError as e:
        return {"status": e.code}
    except Exception as e:
        return {"status": type(e).__name__}


def fib_trie(path="/proc/net/fib_trie", limit=15):
    out = {"exists": os.path.isfile(path), "ips": [], "count": -1}
    if not out["exists"]:
        return out
    try:
        with open(path) as f:
            data = f.read()
    except OSError as e:
        out["err"] = type(e).__name__
        return out
    ips = []
    seen = set()
    for m in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", data):
        if m in seen:
            continue
        seen.add(m)
        ips.append(m)
        if len(ips) >= limit:
            break
    out["ips"] = ips
    out["count"] = len(ips)
    return out


@app.get("/")
def root():
    sock = "/var/run/docker.sock"
    kube_env = sorted(k for k in os.environ if "KUBE" in k.upper())
    sa_info = sa()
    namespaces = None
    own_pods = None
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    if sa_info.get("token_exists"):
        tok = open(token_path).read().strip()
        ns_resp = kube_get("/api/v1/namespaces", tok)
        if ns_resp.get("status") == 200:
            try:
                items = json.loads(ns_resp["body"]).get("items", [])
                namespaces = {
                    "status": 200,
                    "count": len(items),
                    "names": sorted(i.get("metadata", {}).get("name", "?") for i in items),
                }
            except Exception as e:
                namespaces = {"status": 200, "parse_error": type(e).__name__}
        else:
            namespaces = {"status": ns_resp.get("status")}
        ns = sa_info.get("namespace", "")
        if ns:
            pod_resp = kube_get("/api/v1/namespaces/" + ns + "/pods?limit=5", tok)
            if pod_resp.get("status") == 200:
                try:
                    items = json.loads(pod_resp["body"]).get("items", [])
                    own_pods = {"status": 200, "namespace": ns, "count": len(items)}
                except Exception as e:
                    own_pods = {"status": 200, "parse_error": type(e).__name__}
            else:
                own_pods = {"status": pod_resp.get("status"), "namespace": ns}
        # do not return tok
    dns_names = [
        "postgres",
        "minio",
        "garage",
        "registry",
        "grafana",
        "loki",
        "nexus",
        "kubernetes.default.svc",
    ]
    dns_names2 = [
        "kube-dns.kube-system.svc",
        "kube-dns.kube-system.svc.cluster.local",
        "coredns.kube-system.svc.cluster.local",
        "kubernetes.default.svc.cluster.local",
        "registry.kube-system.svc.cluster.local",
        "registry.local",
        "nexus",
        "docker-registry",
        "harbor",
    ]
    registries = [
        "http://192.168.1.150:8081/",
        "http://192.168.1.150:5000/v2/",
        "http://192.168.1.150:8082/",
    ]
    meta = http("http://169.254.169.254/latest/meta-data/")
    kubelet = {}
    for h in ("192.168.1.150", "10.42.0.1"):
        r = tcp(h, 10250)
        kubelet[h] = {"tcp": r}
        if r.get("status") == "open":
            kubelet[h]["healthz"] = kubelet_healthz(h)
    return jsonify(
        probe="net-probe",
        concern="cluster-recon + kube from tenant pod",
        tcp=[{**{"host": h, "port": p, "tag": t}, **tcp(h, p)} for h, p, t in TARGETS],
        kubelet=kubelet,
        dns=[dns(n) for n in dns_names],
        dns_kube=[dns(n) for n in dns_names2],
        registries=[{"url": u, **http(u)} for u in registries],
        fib_trie=fib_trie(),
        kube_api_unauth=kube_unauth_api(),
        listening=[listening_count("/proc/net/tcp"), listening_count("/proc/net/tcp6")],
        docker_sock_exists=os.path.exists(sock),
        kube_env_names=kube_env,
        serviceaccount=sa_info,
        kube_namespaces=namespaces,
        kube_own_pods=own_pods,
        cloud_metadata=meta,
    )


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
