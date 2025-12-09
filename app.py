from flask import Flask, send_from_directory, jsonify, request, session
import os, json, threading, datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv() 

# ---------- CONFIG ----------
# Read admin credentials from environment vars (safer for deployment)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")

if not ADMIN_USERNAME or not ADMIN_PASSWORD or not SECRET_KEY:
    raise RuntimeError(
        "Missing required environment variables. "
        "Please set ADMIN_USERNAME, ADMIN_PASSWORD and FLASK_SECRET_KEY."
    )

# Hash password once at startup
PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)

ATT_FILE = "attendance.json"
# ----------------------------

app = Flask(__name__, static_folder="static", template_folder="static")
app.wsgi_app = ProxyFix(app.wsgi_app)
app.secret_key = SECRET_KEY

file_lock = threading.Lock()

def ensure_att_file():
    if not os.path.exists(ATT_FILE):
        with file_lock:
            with open(ATT_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

def read_attendance():
    ensure_att_file()
    with file_lock:
        with open(ATT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

def write_attendance(data):
    with file_lock:
        with open(ATT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

@app.route("/", methods=["GET"])
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:filename>")
def static_proxy(filename):
    return send_from_directory("static", filename)

# ---------- AUTH ----------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if username == ADMIN_USERNAME and check_password_hash(PASSWORD_HASH, password):
        session.clear()
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"ok": True, "username": username})
    return jsonify({"ok": False, "message": "invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/session", methods=["GET"])
def session_status():
    return jsonify({"logged_in": bool(session.get("logged_in", False)), "username": session.get("username")})

# ---------- CALENDAR API ----------
@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    try:
        year = int(request.args.get("year", datetime.date.today().year))
        month = int(request.args.get("month", datetime.date.today().month))
        assert 1 <= month <= 12
    except Exception:
        return jsonify({"ok": False, "message": "invalid year/month"}), 400

    data = read_attendance()
    first_day = datetime.date(year, month, 1)
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
    days = []
    cur = first_day
    while cur < next_month:
        key = cur.isoformat()
        days.append({
            "date": key,
            "status": data.get(key, {}).get("status", "none"),
            "reason": data.get(key, {}).get("reason", "")
        })
        cur += datetime.timedelta(days=1)
    return jsonify({"ok": True, "year": year, "month": month, "days": days})

# Edit attendance - requires login
@app.route("/api/attendance", methods=["POST"])
def post_attendance():
    if not session.get("logged_in"):
        return jsonify({"ok": False, "message": "unauthorized"}), 401
    payload = request.get_json() or {}
    date_str = payload.get("date")
    status = payload.get("status", "none")  # none, present, exam, leave
    reason = payload.get("reason", "") or ""

    try:
        datetime.date.fromisoformat(date_str)
    except Exception:
        return jsonify({"ok": False, "message": "invalid date format"}), 400

    if status not in ("none", "present", "exam", "leave"):
        return jsonify({"ok": False, "message": "invalid status"}), 400

    data = read_attendance()
    if status == "none":
        if date_str in data:
            data.pop(date_str, None)
    else:
        data[date_str] = {"status": status, "reason": reason}

    write_attendance(data)
    return jsonify({"ok": True, "date": date_str, "status": status, "reason": reason})

if __name__ == "__main__":
    ensure_att_file()
    app.run(host="0.0.0.0", port=5000, debug=True)
