"""
test_app.py – Student Task Manager test suite.

Covers:
  - Home page and UI endpoints
  - Health and status endpoints
  - Task creation: valid input, defaults, whitespace trimming
  - Task creation: validation errors (missing title, bad priority, bad date,
    oversized fields, non-JSON body)
  - Task listing (empty, populated, ordering)
  - Task update / completion (PATCH)
  - Task deletion (DELETE)
  - 404 handling for unknown task IDs
  - Prometheus metrics endpoint
  - Data isolation: failed requests do not corrupt task data

Each test runs against a fresh, temporary SQLite database so the real
application database is never modified.

Compatible with:
  python -m unittest discover -s /tests -v
  python -m xmlrunner discover -s /tests -o /tests/reports
"""

import tempfile
import unittest
from pathlib import Path

import app as student_app


class StudentTaskManagerTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        student_app.DATABASE = Path(self.database_dir.name) / "tasks.db"
        student_app.init_db()
        student_app.app.config.update(TESTING=True)
        self.client = student_app.app.test_client()

    def tearDown(self):
        self.database_dir.cleanup()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def create_task(self, **overrides):
        """POST a task with sensible defaults, overridable per-test."""
        task = {
            "title": "Read chapter 4",
            "course": "Biology",
            "due_date": "2026-11-01",
            "priority": "high",
        }
        task.update(overrides)
        return self.client.post("/api/tasks", json=task)

    # ------------------------------------------------------------------
    # 1. UI / infrastructure endpoints
    # ------------------------------------------------------------------

    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Task Manager", response.data)

    def test_health_endpoint_returns_healthy(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "healthy"})

    def test_status_endpoint_returns_running_and_project_name(self):
        response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "running")
        self.assertEqual(body["project"], "Student Task Manager")

    def test_metrics_endpoint_exposes_prometheus_counter(self):
        # Hit an instrumented endpoint first so the counter is non-zero.
        self.client.get("/api/status")

        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"demo_http_requests_total", response.data)

    def test_metrics_content_type_is_prometheus_text(self):
        response = self.client.get("/metrics")

        self.assertIn("text/plain", response.content_type)

    # ------------------------------------------------------------------
    # 2. Task creation – happy paths
    # ------------------------------------------------------------------

    def test_create_task_returns_201_with_all_fields(self):
        response = self.create_task()

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        for field in ("id", "title", "course", "due_date", "priority", "completed"):
            self.assertIn(field, body, msg=f"Missing field: {field}")

    def test_create_task_stores_correct_values(self):
        response = self.create_task()

        body = response.get_json()
        self.assertEqual(body["title"], "Read chapter 4")
        self.assertEqual(body["priority"], "high")
        self.assertEqual(body["course"], "Biology")
        self.assertEqual(body["due_date"], "2026-11-01")

    def test_create_task_defaults_to_not_completed(self):
        body = self.create_task().get_json()
        self.assertFalse(body["completed"])

    def test_create_task_with_only_title_uses_defaults(self):
        response = self.client.post("/api/tasks", json={"title": "Quick note"})

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["title"], "Quick note")
        self.assertEqual(body["course"], "")
        self.assertEqual(body["due_date"], "")
        self.assertEqual(body["priority"], "medium")

    def test_create_task_strips_whitespace_from_title(self):
        response = self.client.post("/api/tasks", json={"title": "  Trimmed  "})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["title"], "Trimmed")

    def test_create_task_low_priority(self):
        response = self.create_task(priority="low")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["priority"], "low")

    def test_create_task_medium_priority(self):
        response = self.create_task(priority="medium")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["priority"], "medium")

    def test_multiple_tasks_receive_unique_ids(self):
        id1 = self.create_task(title="Task A").get_json()["id"]
        id2 = self.create_task(title="Task B").get_json()["id"]
        self.assertNotEqual(id1, id2)

    # ------------------------------------------------------------------
    # 3. Task creation – validation errors
    # ------------------------------------------------------------------

    def test_create_rejects_empty_title(self):
        response = self.client.post("/api/tasks", json={"title": ""})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_create_rejects_whitespace_only_title(self):
        response = self.client.post("/api/tasks", json={"title": "   "})

        self.assertEqual(response.status_code, 400)

    def test_create_rejects_missing_title_key(self):
        response = self.client.post("/api/tasks", json={"course": "Math"})

        self.assertEqual(response.status_code, 400)

    def test_create_rejects_invalid_priority_values(self):
        for bad_priority in ("urgent", "1", "none", ""):
            with self.subTest(priority=bad_priority):
                response = self.create_task(priority=bad_priority)
                self.assertEqual(response.status_code, 400)

    def test_create_rejects_invalid_due_date_formats(self):
        for bad_date in ("01-11-2026", "2026/11/01", "tomorrow", "not-a-date"):
            with self.subTest(due_date=bad_date):
                response = self.create_task(due_date=bad_date)
                self.assertEqual(response.status_code, 400)

    def test_create_rejects_title_exceeding_120_characters(self):
        response = self.create_task(title="A" * 121)
        self.assertEqual(response.status_code, 400)

    def test_create_accepts_title_at_120_characters(self):
        response = self.create_task(title="B" * 120)
        self.assertEqual(response.status_code, 201)

    def test_create_rejects_course_exceeding_60_characters(self):
        response = self.create_task(course="C" * 61)
        self.assertEqual(response.status_code, 400)

    def test_create_accepts_course_at_60_characters(self):
        response = self.create_task(course="D" * 60)
        self.assertEqual(response.status_code, 201)

    def test_create_rejects_non_json_content_type(self):
        response = self.client.post(
            "/api/tasks",
            content_type="text/plain",
            data="title=hello",
        )
        self.assertEqual(response.status_code, 400)

    def test_failed_validation_does_not_create_task(self):
        """A rejected POST must not leave any partial task in the database."""
        self.create_task(priority="invalid")
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(tasks, [])

    # ------------------------------------------------------------------
    # 4. Listing tasks
    # ------------------------------------------------------------------

    def test_list_tasks_returns_empty_list_on_fresh_database(self):
        response = self.client.get("/api/tasks")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_list_tasks_returns_all_created_tasks(self):
        for i in range(3):
            self.create_task(title=f"Task {i}")

        response = self.client.get("/api/tasks")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 3)

    def test_list_tasks_response_is_json_array(self):
        self.create_task()
        response = self.client.get("/api/tasks")
        self.assertIsInstance(response.get_json(), list)

    def test_list_tasks_incomplete_appear_before_completed(self):
        """Incomplete tasks should be listed before completed ones."""
        id1 = self.create_task(title="Will complete").get_json()["id"]
        self.create_task(title="Stays incomplete")
        self.client.patch(f"/api/tasks/{id1}", json={"completed": True})

        tasks = self.client.get("/api/tasks").get_json()

        self.assertFalse(tasks[0]["completed"])

    def test_list_tasks_includes_all_expected_fields(self):
        self.create_task()
        task = self.client.get("/api/tasks").get_json()[0]

        for field in ("id", "title", "course", "due_date", "priority", "completed"):
            self.assertIn(field, task)

    # ------------------------------------------------------------------
    # 5. Updating tasks (PATCH)
    # ------------------------------------------------------------------

    def test_create_and_list_tasks(self):
        # Preserves the original combined test for backwards compatibility.
        created = self.create_task()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["title"], "Read chapter 4")
        self.assertEqual(created.get_json()["priority"], "high")

        listed = self.client.get("/api/tasks")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()), 1)
        self.assertEqual(listed.get_json()[0]["course"], "Biology")

    def test_mark_task_completed(self):
        task_id = self.create_task().get_json()["id"]

        response = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["completed"])

    def test_mark_task_incomplete_again(self):
        task_id = self.create_task().get_json()["id"]
        self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})

        response = self.client.patch(f"/api/tasks/{task_id}", json={"completed": False})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["completed"])

    def test_patch_reflects_in_list(self):
        task_id = self.create_task().get_json()["id"]
        self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})

        tasks = self.client.get("/api/tasks").get_json()

        self.assertTrue(tasks[0]["completed"])

    def test_patch_nonexistent_task_returns_404(self):
        response = self.client.patch("/api/tasks/99999", json={"completed": True})
        self.assertEqual(response.status_code, 404)

    def test_patch_missing_completed_field_returns_400(self):
        task_id = self.create_task().get_json()["id"]

        response = self.client.patch(f"/api/tasks/{task_id}", json={"priority": "high"})

        self.assertEqual(response.status_code, 400)

    def test_patch_completed_as_string_returns_400(self):
        """completed must be a JSON boolean, not a string representation."""
        task_id = self.create_task().get_json()["id"]

        response = self.client.patch(f"/api/tasks/{task_id}", json={"completed": "true"})

        self.assertEqual(response.status_code, 400)

    def test_patch_returns_updated_task_data(self):
        task_id = self.create_task(title="Verify me").get_json()["id"]

        response = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})
        body = response.get_json()

        self.assertEqual(body["id"], task_id)
        self.assertEqual(body["title"], "Verify me")
        self.assertTrue(body["completed"])

    # ------------------------------------------------------------------
    # 6. Deleting tasks (DELETE)
    # ------------------------------------------------------------------

    def test_task_can_be_completed_and_deleted(self):
        # Original combined test preserved for backwards compatibility.
        task_id = self.create_task().get_json()["id"]

        completed = self.client.patch(
            f"/api/tasks/{task_id}", json={"completed": True}
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.get_json()["completed"])
        self.assertTrue(self.client.get("/api/tasks").get_json()[0]["completed"])

        deleted = self.client.delete(f"/api/tasks/{task_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_delete_existing_task_returns_204_no_body(self):
        task_id = self.create_task().get_json()["id"]

        response = self.client.delete(f"/api/tasks/{task_id}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")

    def test_deleted_task_no_longer_appears_in_list(self):
        task_id = self.create_task().get_json()["id"]
        self.client.delete(f"/api/tasks/{task_id}")

        tasks = self.client.get("/api/tasks").get_json()
        ids = [t["id"] for t in tasks]

        self.assertNotIn(task_id, ids)

    def test_delete_nonexistent_task_returns_404(self):
        response = self.client.delete("/api/tasks/99999")
        self.assertEqual(response.status_code, 404)

    def test_delete_only_removes_targeted_task(self):
        id1 = self.create_task(title="Keep me").get_json()["id"]
        id2 = self.create_task(title="Delete me").get_json()["id"]

        self.client.delete(f"/api/tasks/{id2}")
        tasks = self.client.get("/api/tasks").get_json()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], id1)

    # ------------------------------------------------------------------
    # 7. Full lifecycle integration
    # ------------------------------------------------------------------

    def test_full_lifecycle_create_complete_delete(self):
        """End-to-end: create → list → complete → list → delete → gone."""
        # Create
        resp = self.create_task(title="Lifecycle task", priority="high")
        self.assertEqual(resp.status_code, 201)
        tid = resp.get_json()["id"]

        # Verify listed
        self.assertTrue(
            any(t["id"] == tid for t in self.client.get("/api/tasks").get_json())
        )

        # Complete
        patch_resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": True})
        self.assertTrue(patch_resp.get_json()["completed"])

        # Verify listed as completed
        task = next(
            t for t in self.client.get("/api/tasks").get_json() if t["id"] == tid
        )
        self.assertTrue(task["completed"])

        # Delete
        self.assertEqual(self.client.delete(f"/api/tasks/{tid}").status_code, 204)

        # Verify gone
        self.assertFalse(
            any(t["id"] == tid for t in self.client.get("/api/tasks").get_json())
        )

    def test_completing_one_task_does_not_affect_others(self):
        id_a = self.create_task(title="Task A").get_json()["id"]
        id_b = self.create_task(title="Task B").get_json()["id"]

        self.client.patch(f"/api/tasks/{id_a}", json={"completed": True})

        tasks = {t["id"]: t for t in self.client.get("/api/tasks").get_json()}
        self.assertTrue(tasks[id_a]["completed"])
        self.assertFalse(tasks[id_b]["completed"])


if __name__ == "__main__":
    unittest.main()
