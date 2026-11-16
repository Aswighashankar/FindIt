from flask import Flask, request, redirect, url_for, session, flash, render_template, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
from datetime import datetime
import sqlite3, os

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "findit.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("FINDIT_SECRET_KEY", "change-this-local-demo-key")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        );
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            report_type TEXT NOT NULL,
            report_date TEXT NOT NULL,
            photo TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            claimant_id INTEGER NOT NULL,
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY(report_id) REFERENCES reports(id),
            FOREIGN KEY(claimant_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
init_db()

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def notify(user_id, message):
    with connect_db() as db:
        db.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",
                   (user_id, message, now()))

def logged_in(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access is required.")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def page(title, template, **kwargs):
    return render_template(template, title=title, **kwargs)

@app.route("/")
def home():
    with connect_db() as db:
        total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        lost = db.execute("SELECT COUNT(*) FROM reports WHERE report_type='LOST' AND status='open'").fetchone()[0]
        found = db.execute("SELECT COUNT(*) FROM reports WHERE report_type='FOUND' AND status='open'").fetchone()[0]
    return page("FindIt", "home.html", total=total, lost=lost, found=found)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter all details. Password must contain at least 8 characters.")
            return redirect(url_for("register"))
        try:
            with connect_db() as db:
                db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,'student')",
                           (name, email, generate_password_hash(password)))
            flash("Account created. Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.")
    return page("Create account", "register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Incorrect email or password.")
    return page("Log in", "login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))

@app.route("/dashboard")
@logged_in
def dashboard():
    uid = session["user_id"]
    with connect_db() as db:
        reports = db.execute("SELECT * FROM reports WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
        lost_reports = db.execute("SELECT * FROM reports WHERE user_id=? AND report_type='LOST' AND status='open'", (uid,)).fetchall()
        found_reports = db.execute("SELECT * FROM reports WHERE report_type='FOUND' AND status='open' ORDER BY id DESC").fetchall()
        notifications = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        claims = db.execute("""SELECT c.*,r.item_name FROM claims c JOIN reports r ON c.report_id=r.id
                               WHERE c.claimant_id=? ORDER BY c.id DESC""", (uid,)).fetchall()
    matches = []
    for lost in lost_reports:
        for found in found_reports:
            if lost["id"] == found["id"] or lost["user_id"] == found["user_id"]:
                continue
            score = 0
            if lost["category"].lower() == found["category"].lower(): score += 35
            if lost["item_name"].lower() in found["item_name"].lower() or found["item_name"].lower() in lost["item_name"].lower(): score += 30
            words1 = set(lost["description"].lower().split())
            words2 = set(found["description"].lower().split())
            if words1 or words2: score += int(20 * len(words1 & words2) / max(1, len(words1 | words2)))
            if lost["location"].lower() == found["location"].lower(): score += 15
            if score >= 35:
                matches.append({"lost": lost, "found": found, "score": score})
    matches.sort(key=lambda x: x["score"], reverse=True)
    return page("Student dashboard", "dashboard.html", reports=reports, matches=matches[:10],
                notifications=notifications, claims=claims)

@app.route("/report", methods=["GET", "POST"])
@logged_in
def report():
    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        report_type = request.form.get("report_type", "")
        report_date = request.form.get("report_date", "")
        photo_name = None
        photo = request.files.get("photo")
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Photo must be PNG, JPG, JPEG or WEBP.")
                return redirect(url_for("report"))
            safe_name = secure_filename(f"{session['user_id']}_{int(datetime.now().timestamp())}_{photo.filename}")
            photo.save(UPLOAD_DIR / safe_name)
            photo_name = safe_name
        if not all([item_name, category, description, location, report_date]) or report_type not in ["LOST", "FOUND"]:
            flash("Please complete all required fields.")
            return redirect(url_for("report"))
        with connect_db() as db:
            db.execute("""INSERT INTO reports(user_id,item_name,category,description,location,report_type,
                          report_date,photo,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                       (session["user_id"], item_name, category, description, location, report_type,
                        report_date, photo_name, now()))
        flash("Your report has been submitted.")
        return redirect(url_for("dashboard"))
    return page("Report an item", "report.html")

@app.route("/claim/<int:report_id>", methods=["POST"])
@logged_in
def claim(report_id):
    details = request.form.get("details", "").strip()
    with connect_db() as db:
        found = db.execute("SELECT * FROM reports WHERE id=? AND report_type='FOUND' AND status='open'", (report_id,)).fetchone()
        if not found or found["user_id"] == session["user_id"] or not details:
            flash("This claim cannot be submitted. Check the report and add identifying details.")
            return redirect(url_for("dashboard"))
        db.execute("INSERT INTO claims(report_id,claimant_id,details,created_at) VALUES(?,?,?,?)",
                   (report_id, session["user_id"], details, now()))
        db.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",
                   (found["user_id"], f"Someone submitted a claim for your found item: {found['item_name']}.", now()))
    flash("Claim submitted for admin review. A match is not proof of ownership.")
    return redirect(url_for("dashboard"))

@app.route("/admin")
@admin_only
def admin_dashboard():
    with connect_db() as db:
        reports = db.execute("""SELECT r.*,u.name AS reporter FROM reports r JOIN users u ON r.user_id=u.id
                                ORDER BY r.id DESC""").fetchall()
        claims = db.execute("""SELECT c.*,r.item_name,u.name AS claimant FROM claims c
                               JOIN reports r ON c.report_id=r.id JOIN users u ON c.claimant_id=u.id
                               ORDER BY c.id DESC""").fetchall()
        stats = {
            "reports": db.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
            "lost": db.execute("SELECT COUNT(*) FROM reports WHERE report_type='LOST'").fetchone()[0],
            "found": db.execute("SELECT COUNT(*) FROM reports WHERE report_type='FOUND'").fetchone()[0],
            "pending": db.execute("SELECT COUNT(*) FROM claims WHERE status='pending'").fetchone()[0]
        }
    return page("Admin dashboard", "admin.html", reports=reports, claims=claims, stats=stats)

@app.route("/admin/claim/<int:claim_id>", methods=["POST"])
@admin_only
def review_claim(claim_id):
    status = request.form.get("status")
    note = request.form.get("note", "").strip()
    if status not in ["approved", "rejected", "completed"]:
        flash("Invalid claim status.")
        return redirect(url_for("admin_dashboard"))
    with connect_db() as db:
        claim_row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if not claim_row:
            flash("Claim not found.")
            return redirect(url_for("admin_dashboard"))
        db.execute("UPDATE claims SET status=?,admin_note=? WHERE id=?", (status, note, claim_id))
        db.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",
                   (claim_row["claimant_id"], f"Your claim status is now {status}. {note}", now()))
        if status == "completed":
            db.execute("UPDATE reports SET status='closed' WHERE id=?", (claim_row["report_id"],))
    flash("Claim review updated.")
    return redirect(url_for("admin_dashboard"))

@app.route("/photo/<filename>")
@logged_in
def photo(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)