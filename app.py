import os
from contextlib import contextmanager
from datetime import date, datetime

import pymysql
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to see your tasks."

PRIORITIES = ("low", "medium", "high")


# ---------- Database helpers ----------
def connect():
    config = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "taskdb"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    if os.getenv("DB_SSL_CA"):
        config["ssl_ca"] = os.getenv("DB_SSL_CA")
    return pymysql.connect(**config)


@contextmanager
def get_cursor():
    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def init_db():
    """Create the users and tasks tables if they do not exist."""
    with get_cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                done TINYINT(1) NOT NULL DEFAULT 0,
                due_date DATE NULL,
                priority ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )"""
        )


# ---------- Flask-Login setup ----------
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    with get_cursor() as cur:
        cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return User(row["id"], row["username"]) if row else None


# ---------- Auth routes ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not 3 <= len(username) <= 50:
            flash("Username must be 3 to 50 characters.")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.")
        else:
            try:
                with get_cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                        (username, generate_password_hash(password)),
                    )
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except pymysql.err.IntegrityError:
                flash("That username is already taken.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()

        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row["id"], row["username"]))
            return redirect(url_for("index"))
        flash("Invalid username or password.")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# ---------- Task routes ----------
@app.route("/")
@login_required
def index():
    """Unfinished first, then earliest due date (no date last), then high priority first."""
    with get_cursor() as cur:
        cur.execute(
            """SELECT * FROM tasks
               WHERE user_id = %s
               ORDER BY done,
                        due_date IS NULL,
                        due_date,
                        FIELD(priority, 'high', 'medium', 'low'),
                        id DESC""",
            (current_user.id,),
        )
        tasks = cur.fetchall()
    return render_template("index.html", tasks=tasks, today=date.today())


@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("index"))

    # Only accept known priorities; fall back to medium
    priority = request.form.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"

    # The date box sends text like 2026-11-05; empty or invalid means no due date
    due_raw = request.form.get("due_date", "").strip()
    try:
        due_date = datetime.strptime(due_raw, "%Y-%m-%d").date() if due_raw else None
    except ValueError:
        due_date = None

    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO tasks (user_id, title, due_date, priority) VALUES (%s, %s, %s, %s)",
            (current_user.id, title, due_date, priority),
        )
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>", methods=["POST"])
@login_required
def toggle(task_id):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE tasks SET done = 1 - done WHERE id = %s AND user_id = %s",
            (task_id, current_user.id),
        )
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete(task_id):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, current_user.id),
        )
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)