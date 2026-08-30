import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def root():
    url = os.environ.get("DATABASE_URL")
    out = {
        "probe": "pg-probe",
        "has_database_url": bool(url),
        "current_database": None,
        "current_user": None,
        "datnames": None,
        "error": None,
    }
    if not url:
        return jsonify(out)
    try:
        import psycopg2

        conn = psycopg2.connect(url)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user")
        out["current_database"], out["current_user"] = cur.fetchone()
        cur.execute("SELECT datname FROM pg_database ORDER BY 1")
        out["datnames"] = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        out["error"] = type(e).__name__ + ": " + str(e)[:200]
    return jsonify(out)


@app.get("/health")
def health():
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
