from datetime import date

import app as app_module

db = app_module.db
User = app_module.User
Task = app_module.Task

PASSWORD = "secret123"


# ---------- Helper functions ----------
def register(client, username="alice", password=PASSWORD):
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def login(client, username="alice", password=PASSWORD):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def register_and_login(client, username="alice"):
    register(client, username)
    return login(client, username)


def add_task(client, title="Buy milk", **extra):
    return client.post("/add", data={"title": title, **extra}, follow_redirects=True)


def edit_task(client, task_id, **data):
    return client.post(f"/edit/{task_id}", data=data, follow_redirects=True)


def all_tasks():
    """Read tasks straight from the database as plain dictionaries."""
    with app_module.app.app_context():
        rows = db.session.scalars(db.select(Task).order_by(Task.id)).all()
        return [
            dict(
                id=t.id,
                title=t.title,
                done=t.done,
                due_date=t.due_date,
                priority=t.priority,
            )
            for t in rows
        ]


def count_users():
    with app_module.app.app_context():
        return db.session.scalar(db.select(db.func.count()).select_from(User))


# ---------- Registration and login ----------
def test_register_creates_account(client):
    response = register(client)
    assert b"Account created" in response.data

    with app_module.app.app_context():
        users = db.session.scalars(db.select(User)).all()
        assert len(users) == 1
        assert users[0].username == "alice"
        assert users[0].password_hash != PASSWORD  # stored hashed, not as plain text


def test_duplicate_username_rejected(client):
    register(client)
    response = register(client)
    assert b"already taken" in response.data
    assert count_users() == 1


def test_short_password_rejected(client):
    response = register(client, "bob", "123")
    assert b"at least 6" in response.data
    assert count_users() == 0


def test_login_success(client):
    register(client)
    response = login(client)
    assert b"Logout (alice)" in response.data


def test_login_wrong_password(client):
    register(client)
    response = login(client, password="wrong-password")
    assert b"Invalid username or password" in response.data


def test_index_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout(client):
    register_and_login(client)
    response = client.post("/logout", follow_redirects=True)
    assert b"logged out" in response.data
    assert client.get("/").status_code == 302  # sent back to login


# ---------- Adding tasks ----------
def test_add_task_uses_defaults(client):
    register_and_login(client)
    response = add_task(client, "Buy milk")

    tasks = all_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Buy milk"
    assert tasks[0]["priority"] == "medium"
    assert tasks[0]["due_date"] is None
    assert tasks[0]["done"] is False
    assert b"Buy milk" in response.data


def test_add_task_with_priority_and_due_date(client):
    register_and_login(client)
    response = add_task(client, "Pay rent", priority="high", due_date="2030-01-01")

    task = all_tasks()[0]
    assert task["priority"] == "high"
    assert task["due_date"] == date(2030, 1, 1)
    assert b"High" in response.data
    assert b"01 Jan 2030" in response.data


def test_empty_title_not_added(client):
    register_and_login(client)
    add_task(client, "   ")
    assert all_tasks() == []


def test_invalid_priority_falls_back_to_medium(client):
    register_and_login(client)
    add_task(client, "Task", priority="urgent")
    assert all_tasks()[0]["priority"] == "medium"


def test_invalid_due_date_is_ignored(client):
    register_and_login(client)
    add_task(client, "Task", due_date="not-a-date")
    assert all_tasks()[0]["due_date"] is None


# ---------- Done / delete ----------
def test_toggle_task(client):
    register_and_login(client)
    add_task(client)
    task_id = all_tasks()[0]["id"]

    client.post(f"/toggle/{task_id}")
    assert all_tasks()[0]["done"] is True

    client.post(f"/toggle/{task_id}")
    assert all_tasks()[0]["done"] is False


def test_delete_task(client):
    register_and_login(client)
    add_task(client)
    task_id = all_tasks()[0]["id"]

    client.post(f"/delete/{task_id}")
    assert all_tasks() == []


def test_toggle_and_delete_need_post(client):
    register_and_login(client)
    add_task(client)
    task_id = all_tasks()[0]["id"]

    assert client.get(f"/toggle/{task_id}").status_code == 405  # Method Not Allowed
    assert client.get(f"/delete/{task_id}").status_code == 405
    assert len(all_tasks()) == 1


# ---------- Users stay separate ----------
def test_user_cannot_touch_other_users_tasks(client, other_client):
    register_and_login(client, "alice")
    add_task(client, "Alice secret task")
    task_id = all_tasks()[0]["id"]

    register_and_login(other_client, "bob")

    # Bob does not see Alice's task
    assert b"Alice secret task" not in other_client.get("/").data

    # Bob cannot toggle or delete it by guessing the id
    assert other_client.post(f"/toggle/{task_id}").status_code == 404
    assert other_client.post(f"/delete/{task_id}").status_code == 404

    tasks = all_tasks()
    assert len(tasks) == 1
    assert tasks[0]["done"] is False


# ---------- Due dates and sorting ----------
def test_overdue_label(client):
    register_and_login(client)
    add_task(client, "Old task", due_date="2000-01-01")
    task_id = all_tasks()[0]["id"]

    assert b"(overdue)" in client.get("/").data

    client.post(f"/toggle/{task_id}")  # finished tasks are never overdue
    assert b"(overdue)" not in client.get("/").data


def test_task_ordering(client):
    register_and_login(client)
    add_task(client, "TaskUndated")
    add_task(client, "TaskLater", due_date="2030-02-01")
    add_task(client, "TaskSooner", due_date="2030-01-01")

    page = client.get("/").data.decode()
    # Earliest due date first, tasks without a date last
    assert page.index("TaskSooner") < page.index("TaskLater") < page.index("TaskUndated")


# ---------- Editing tasks ----------
def test_edit_page_is_prefilled(client):
    register_and_login(client)
    add_task(client, "Buy milk", priority="high", due_date="2030-01-01")
    task_id = all_tasks()[0]["id"]

    page = client.get(f"/edit/{task_id}").data
    assert b'value="Buy milk"' in page
    assert b'value="2030-01-01"' in page


def test_edit_updates_task(client):
    register_and_login(client)
    add_task(client, "Old title")
    task_id = all_tasks()[0]["id"]

    edit_task(client, task_id, title="New title", priority="low", due_date="2031-05-06")

    task = all_tasks()[0]
    assert task["title"] == "New title"
    assert task["priority"] == "low"
    assert task["due_date"] == date(2031, 5, 6)


def test_edit_can_clear_due_date(client):
    register_and_login(client)
    add_task(client, "Task", due_date="2030-01-01")
    task_id = all_tasks()[0]["id"]

    edit_task(client, task_id, title="Task", priority="medium", due_date="")
    assert all_tasks()[0]["due_date"] is None


def test_edit_empty_title_rejected(client):
    register_and_login(client)
    add_task(client, "Keep me")
    task_id = all_tasks()[0]["id"]

    response = edit_task(client, task_id, title="   ", priority="high")
    assert b"cannot be empty" in response.data
    assert all_tasks()[0]["title"] == "Keep me"


def test_edit_requires_login(client):
    assert client.get("/edit/1").status_code == 302


def test_cannot_edit_other_users_task(client, other_client):
    register_and_login(client, "alice")
    add_task(client, "Alice task")
    task_id = all_tasks()[0]["id"]

    register_and_login(other_client, "bob")
    assert other_client.get(f"/edit/{task_id}").status_code == 404
    assert other_client.post(f"/edit/{task_id}", data={"title": "Hacked"}).status_code == 404
    assert all_tasks()[0]["title"] == "Alice task"