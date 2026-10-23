import os
from contextlib import contextmanager

import pymysql
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

load_dotenv()  # reads values from the .env file

app = Flask(__name__)


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
    # Hosted MySQL services often require SSL; set DB_SSL_CA to the CA file path
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
    with get_cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                done TINYINT(1) NOT NULL DEFAULT 0
            )"""
        )


@app.route("/")
def index():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM tasks ORDER BY done, id DESC")
        tasks = cur.fetchall()
    return render_template("index.html", tasks=tasks)


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    if title:
        with get_cursor() as cur:
            cur.execute("INSERT INTO tasks (title) VALUES (%s)", (title,))
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>")
def toggle(task_id):
    with get_cursor() as cur:
        cur.execute("UPDATE tasks SET done = 1 - done WHERE id = %s", (task_id,))
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>")
def delete(task_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
