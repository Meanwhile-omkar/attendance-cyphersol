from flask import Flask, send_from_directory, jsonify, request, session
import os
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIG ==================
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not ADMIN_USERNAME or not ADMIN_PASSWORD or not SECRET_KEY or not DATABASE_URL:
    raise RuntimeError(
        "Missing required environment variables. "
        "Set ADMIN_USERNAME, ADMIN_PASSWORD, FLASK_SECRET_KEY, DATABASE_URL"
    )

PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)

# ================== APP ==================
app = Flask(__name__, static_folder="static", template_folder="static")
app.wsgi_app = ProxyFix(app.wsgi_app)
app.secret_key = SECRET_KEY

# ================== DB ==================
def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor
    )

# ================== STATIC ==================
@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:filename>")
def static_proxy(filename):
    return send_from_directory("static", filename)

# ================== AUTH ==================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    if (
        data.get("username") == ADMIN_USERNAME
        and check_password_hash(PASSWORD_HASH, data.get("password", ""))
    ):
        session.clear()
        session["logged_in"] = True
        session["username"] = ADMIN_USERNAME
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/session", methods=["GET"])
def session_status():
    return jsonify({
        "logged_in": bool(session.get("logged_in")),
        "username": session.get("username")
    })

# ================== CALENDAR ==================
@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    try:
        year = int(request.args.get("year", datetime.date.today().year))
        month = int(request.args.get("month", datetime.date.today().month))
        assert 1 <= month <= 12
    except Exception:
        return jsonify({"ok": False, "message": "invalid year/month"}), 400

    start_date = datetime.date(year, month, 1)
    end_date = (
        datetime.date(year + 1, 1, 1)
        if month == 12
        else datetime.date(year, month + 1, 1)
    )

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT date, status, reason
        FROM attendance
        WHERE date >= %s AND date < %s
        """,
        (start_date, end_date),
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    db_data = {row["date"].isoformat(): row for row in rows}

    days = []
    current = start_date
    while current < end_date:
        key = current.isoformat()
        days.append({
            "date": key,
            "status": db_data.get(key, {}).get("status", "none"),
            "reason": db_data.get(key, {}).get("reason", "")
        })
        current += datetime.timedelta(days=1)

    return jsonify({
        "ok": True,
        "year": year,
        "month": month,
        "days": days
    })

# ================== ATTENDANCE ==================
@app.route("/api/attendance", methods=["POST"])
def post_attendance():
    if not session.get("logged_in"):
        return jsonify({"ok": False, "message": "unauthorized"}), 401

    payload = request.get_json() or {}
    date_str = payload.get("date")
    status = payload.get("status", "none")
    reason = payload.get("reason", "") or ""

    try:
        datetime.date.fromisoformat(date_str)
    except Exception:
        return jsonify({"ok": False, "message": "invalid date"}), 400

    if status not in ("none", "present", "exam", "leave"):
        return jsonify({"ok": False, "message": "invalid status"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    if status == "none":
        cur.execute("DELETE FROM attendance WHERE date = %s", (date_str,))
    else:
        cur.execute(
            """
            INSERT INTO attendance (date, status, reason)
            VALUES (%s, %s, %s)
            ON CONFLICT (date)
            DO UPDATE SET
                status = EXCLUDED.status,
                reason = EXCLUDED.reason,
                updated_at = CURRENT_TIMESTAMP
            """,
            (date_str, status, reason),
        )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "ok": True,
        "date": date_str,
        "status": status,
        "reason": reason
    })

# ================== MAIN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
