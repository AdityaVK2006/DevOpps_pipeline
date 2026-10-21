import os
import sqlite3
from datetime import date
from pathlib import Path
from contextlib import contextmanager

from flask import Flask, Response, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

app = Flask(__name__)
REQUESTS = Counter("demo_http_requests_total", "HTTP requests handled", ["path"])
DATABASE = Path(os.environ.get("TASKS_DB", Path(__file__).with_name("student_tasks.db")))


@contextmanager
def connect_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    with connect_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'medium',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )


init_db()


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "course": row["course"],
        "due_date": row["due_date"],
        "priority": row["priority"],
        "completed": bool(row["completed"]),
    }


@app.get("/")
def home():
    REQUESTS.labels(path="/").inc()
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    REQUESTS.labels(path="/api/status").inc()
    return jsonify(status="running", project="Student Task Manager")


@app.get("/api/tasks")
def list_tasks():
    REQUESTS.labels(path="/api/tasks").inc()
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks ORDER BY completed ASC, due_date = '' ASC, due_date ASC, id DESC"
        ).fetchall()
    return jsonify([task_json(row) for row in rows])


@app.post("/api/tasks")
def create_task():
    REQUESTS.labels(path="/api/tasks").inc()
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    course = str(data.get("course", "")).strip()
    due_date = str(data.get("due_date", "")).strip()
    priority = str(data.get("priority", "medium")).strip().lower()

    if not title:
        return jsonify(error="Add a task title."), 400
    if len(title) > 120 or len(course) > 60:
        return jsonify(error="Title must be 120 characters or less and course 60 or less."), 400
    if priority not in {"low", "medium", "high"}:
        return jsonify(error="Choose low, medium, or high priority."), 400
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            return jsonify(error="Enter a valid due date."), 400

    with connect_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, course, due_date, priority) VALUES (?, ?, ?, ?)",
            (title, course, due_date, priority),
        )
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(task_json(row)), 201


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    REQUESTS.labels(path="/api/tasks").inc()
    data = request.get_json(silent=True) or {}
    if "completed" not in data or not isinstance(data["completed"], bool):
        return jsonify(error="A completed true/false value is required."), 400

    with connect_db() as connection:
        cursor = connection.execute(
            "UPDATE tasks SET completed = ? WHERE id = ?", (int(data["completed"]), task_id)
        )
        if cursor.rowcount == 0:
            return jsonify(error="Task not found."), 404
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(task_json(row))


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    REQUESTS.labels(path="/api/tasks").inc()
    with connect_db() as connection:
        cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cursor.rowcount == 0:
        return jsonify(error="Task not found."), 404
    return "", 204


@app.get("/health")
def health():
    return jsonify(status="healthy")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
