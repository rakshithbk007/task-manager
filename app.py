import os
from datetime import date, datetime

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
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

PRIORITIES = ("low", "medium", "high")

# ---------- Database configuration ----------
# URL.create builds the connection URL safely, even if your password has special characters
app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME", "taskdb"),
)

engine_options = {
    "pool_pre_ping": True,  # test a connection before using it (avoids "MySQL has gone away")
    "pool_recycle": 280,    # replace connections before the server closes idle ones
}
# Hosted MySQL often needs SSL: set DB_SSL_CA to the certificate path
if os.getenv("DB_SSL_CA"):
    engine_options["connect_args"] = {"ssl_ca": os.getenv("DB_SSL_CA")}
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to see your tasks."


# ---------- Models (each class is one table) ----------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(255), nullable=False)
    done = db.Column(db.Boolean, nullable=False, default=False)
    due_date = db.Column(db.Date, nullable=True)
    priority = db.Column(db.Enum(*PRIORITIES, name="priority"), nullable=False, default="medium")


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on every request to turn the cookie into a User."""
    return db.session.get(User, int(user_id))


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
            db.session.add(
                User(username=username, password_hash=generate_password_hash(password))
            )
            try:
                db.session.commit()
            except IntegrityError:  # the UNIQUE rule on username was broken
                db.session.rollback()
                flash("That username is already taken.")
            else:
                flash("Account created. Please log in.")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.session.scalar(db.select(User).where(User.username == username))
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
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
def parse_task_form():
    """Read and clean title, priority and due date from a submitted form."""
    title = request.form.get("title", "").strip()[:255]  # column holds 255 characters max

    priority = request.form.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"

    # Empty or invalid date means "no due date"
    due_raw = request.form.get("due_date", "").strip()
    try:
        due_date = datetime.strptime(due_raw, "%Y-%m-%d").date() if due_raw else None
    except ValueError:
        due_date = None

    return title, priority, due_date


def get_own_task_or_404(task_id):
    """Find a task by id, but only if it belongs to the logged-in user."""
    return db.first_or_404(
        db.select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )


@app.route("/")
@login_required
def index():
    """Unfinished first, then earliest due date (no date last), then high priority first."""
    tasks = db.session.scalars(
        db.select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(
            Task.done,
            Task.due_date.is_(None),
            Task.due_date,
            func.field(Task.priority, "high", "medium", "low"),  # MySQL FIELD() function
            Task.id.desc(),
        )
    ).all()
    return render_template("index.html", tasks=tasks, today=date.today())


@app.route("/add", methods=["POST"])
@login_required
def add():
    title, priority, due_date = parse_task_form()
    if title:
        db.session.add(
            Task(user_id=current_user.id, title=title, due_date=due_date, priority=priority)
        )
        db.session.commit()
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>", methods=["POST"])
@login_required
def toggle(task_id):
    task = get_own_task_or_404(task_id)
    task.done = not task.done
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete(task_id):
    task = get_own_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit(task_id):
    task = get_own_task_or_404(task_id)

    if request.method == "POST":
        title, priority, due_date = parse_task_form()
        if not title:
            flash("Title cannot be empty.")
            return render_template("edit.html", task=task)

        task.title = title
        task.priority = priority
        task.due_date = due_date
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("edit.html", task=task)


# Create any missing tables when the app starts (existing tables are left untouched)
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)