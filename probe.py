import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

TARGETS = [
    ("192.168.1.150", 5432),
    ("192.168.1.150", 3900),
    ("192.168.1.150", 10250),
    ("kubernetes.default.svc", 443),
    ("169.254.169.254", 80),
]

ENV_HINTS = ("KUBE", "KAD", "TOKEN", "S3", "DATABASE")


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


def probe():
    docker_sock = os.path.exists("/var/run/docker.sock")
    sa_token = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    token_exists = os.path.exists(sa_token)
    token_len = None
    if token_exists:
        try:
            with open(sa_token) as f:
                token_len = len(f.read().strip())
        except OSError:
            token_len = -1

    tcp = {}
    for host, port in TARGETS:
        tcp[f"{host}:{port}"] = tcp_check(host, port)

    env_keys = sorted(
        k for k in os.environ.keys() if any(h in k.upper() for h in ENV_HINTS)
    )

    return {
        "probe_ts": int(time.time()),
        "docker_sock_exists": docker_sock,
        "sa_token_exists": token_exists,
        "sa_token_len": token_len,
        "tcp": tcp,
        "env_key_names": env_keys,
        "unauth_kube_api": https_get_noauth("https://kubernetes.default.svc/api"),
    }


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))