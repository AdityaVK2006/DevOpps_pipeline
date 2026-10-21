"""
test_tasks_advanced.py
======================
Extended test suite for the Student Task Manager Flask API.
Covers edge cases, field validation, ordering, and API contract checks.

Run locally:
    python -m unittest discover -s tests -v

Run in Jenkins (via Jenkinsfile):
    docker run --rm -v "$WORKSPACE/tests:/tests:ro" "$APP_IMAGE" \
        python -m unittest discover -s /tests -v
"""

import json
import tempfile
import unittest
from pathlib import Path

import app as student_app


# ---------------------------------------------------------------------------
# Base test class – each test method gets a clean, empty SQLite database.
# ---------------------------------------------------------------------------
class BaseTaskTest(unittest.TestCase):
    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory()
        student_app.DATABASE = Path(self.db_dir.name) / "tasks_test.db"
        student_app.init_db()
        student_app.app.config.update(TESTING=True)
        self.client = student_app.app.test_client()

    def tearDown(self):
        self.db_dir.cleanup()

    # Helper – post a task with sensible defaults, overridable per-test.
    def make_task(self, **overrides):
        payload = {
            "title": "Submit lab report",
            "course": "Chemistry",
            "due_date": "2026-12-01",
            "priority": "medium",
        }
        payload.update(overrides)
        return self.client.post("/api/tasks", json=payload)

    def task_id(self, **overrides):
        """Create a task and return its ID."""
        return self.make_task(**overrides).get_json()["id"]


# ---------------------------------------------------------------------------
# 1. Task creation – happy paths
# ---------------------------------------------------------------------------
class TestTaskCreation(BaseTaskTest):

    def test_create_returns_201_and_all_fields(self):
        """A successful POST must return 201 with every expected field."""
        resp = self.make_task()
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        for field in ("id", "title", "course", "due_date", "priority", "completed"):
            self.assertIn(field, body, msg=f"Missing field: {field}")

    def test_create_task_without_optional_fields(self):
        """course and due_date are optional; only title is mandatory."""
        resp = self.client.post("/api/tasks", json={"title": "Quick note"})
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertEqual(body["title"], "Quick note")
        self.assertEqual(body["course"], "")
        self.assertEqual(body["due_date"], "")

    def test_create_sets_completed_false_by_default(self):
        """Newly created tasks must not be marked completed."""
        body = self.make_task().get_json()
        self.assertFalse(body["completed"])

    def test_create_low_priority_task(self):
        resp = self.make_task(priority="low")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["priority"], "low")

    def test_create_high_priority_task(self):
        resp = self.make_task(priority="high")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["priority"], "high")

    def test_title_is_stripped_of_whitespace(self):
        """Leading/trailing whitespace in title should be stripped."""
        resp = self.client.post("/api/tasks", json={"title": "  Trimmed Title  "})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["title"], "Trimmed Title")

    def test_multiple_tasks_receive_unique_ids(self):
        """Each task must get a distinct database ID."""
        id1 = self.make_task(title="Task A").get_json()["id"]
        id2 = self.make_task(title="Task B").get_json()["id"]
        self.assertNotEqual(id1, id2)


# ---------------------------------------------------------------------------
# 2. Task creation – validation / rejection
# ---------------------------------------------------------------------------
class TestTaskValidation(BaseTaskTest):

    def test_empty_title_rejected(self):
        resp = self.client.post("/api/tasks", json={"title": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_whitespace_only_title_rejected(self):
        resp = self.client.post("/api/tasks", json={"title": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_missing_title_key_rejected(self):
        resp = self.client.post("/api/tasks", json={"course": "Math"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_priority_values_rejected(self):
        for bad in ("urgent", "MEDIUM", "1", "", "none"):
            with self.subTest(priority=bad):
                resp = self.make_task(priority=bad)
                self.assertEqual(resp.status_code, 400)

    def test_invalid_due_date_formats_rejected(self):
        for bad in ("01-12-2026", "2026/12/01", "tomorrow", "not-a-date"):
            with self.subTest(due_date=bad):
                resp = self.make_task(due_date=bad)
                self.assertEqual(resp.status_code, 400)

    def test_title_too_long_rejected(self):
        resp = self.make_task(title="A" * 121)
        self.assertEqual(resp.status_code, 400)

    def test_course_too_long_rejected(self):
        resp = self.make_task(course="C" * 61)
        self.assertEqual(resp.status_code, 400)

    def test_title_at_max_length_accepted(self):
        resp = self.make_task(title="B" * 120)
        self.assertEqual(resp.status_code, 201)

    def test_course_at_max_length_accepted(self):
        resp = self.make_task(course="D" * 60)
        self.assertEqual(resp.status_code, 201)

    def test_non_json_body_returns_400(self):
        resp = self.client.post(
            "/api/tasks",
            content_type="text/plain",
            data="title=hello",
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 3. Listing tasks
# ---------------------------------------------------------------------------
class TestListTasks(BaseTaskTest):

    def test_empty_list_on_fresh_database(self):
        resp = self.client.get("/api/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_all_created_tasks_are_returned(self):
        for i in range(3):
            self.make_task(title=f"Task {i}")
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 3)

    def test_list_response_is_json_array(self):
        self.make_task()
        resp = self.client.get("/api/tasks")
        self.assertIsInstance(resp.get_json(), list)

    def test_incomplete_tasks_appear_before_completed(self):
        """Incomplete tasks should come before completed ones in the list."""
        id1 = self.task_id(title="Will complete")
        self.task_id(title="Will stay incomplete")
        self.client.patch(f"/api/tasks/{id1}", json={"completed": True})

        tasks = self.client.get("/api/tasks").get_json()
        # The first task in the list should not be completed
        self.assertFalse(tasks[0]["completed"])


# ---------------------------------------------------------------------------
# 4. Updating tasks (PATCH)
# ---------------------------------------------------------------------------
class TestUpdateTask(BaseTaskTest):

    def test_mark_task_completed(self):
        tid = self.task_id()
        resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": True})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["completed"])

    def test_mark_task_incomplete_again(self):
        tid = self.task_id()
        self.client.patch(f"/api/tasks/{tid}", json={"completed": True})
        resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": False})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["completed"])

    def test_patch_nonexistent_task_returns_404(self):
        resp = self.client.patch("/api/tasks/99999", json={"completed": True})
        self.assertEqual(resp.status_code, 404)

    def test_patch_missing_completed_field_returns_400(self):
        tid = self.task_id()
        resp = self.client.patch(f"/api/tasks/{tid}", json={"priority": "high"})
        self.assertEqual(resp.status_code, 400)

    def test_patch_completed_as_string_returns_400(self):
        """completed must be a JSON boolean, not a string."""
        tid = self.task_id()
        resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": "true"})
        self.assertEqual(resp.status_code, 400)

    def test_patch_returns_updated_task_data(self):
        tid = self.task_id(title="Check me")
        resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": True})
        body = resp.get_json()
        self.assertEqual(body["id"], tid)
        self.assertEqual(body["title"], "Check me")


# ---------------------------------------------------------------------------
# 5. Deleting tasks
# ---------------------------------------------------------------------------
class TestDeleteTask(BaseTaskTest):

    def test_delete_existing_task_returns_204(self):
        tid = self.task_id()
        resp = self.client.delete(f"/api/tasks/{tid}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp.data, b"")

    def test_deleted_task_no_longer_listed(self):
        tid = self.task_id()
        self.client.delete(f"/api/tasks/{tid}")
        tasks = self.client.get("/api/tasks").get_json()
        ids = [t["id"] for t in tasks]
        self.assertNotIn(tid, ids)

    def test_delete_nonexistent_task_returns_404(self):
        resp = self.client.delete("/api/tasks/99999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_only_removes_targeted_task(self):
        id1 = self.task_id(title="Keep me")
        id2 = self.task_id(title="Delete me")
        self.client.delete(f"/api/tasks/{id2}")
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], id1)


# ---------------------------------------------------------------------------
# 6. Infrastructure / observability endpoints
# ---------------------------------------------------------------------------
class TestInfraEndpoints(BaseTaskTest):

    def test_health_endpoint_returns_healthy(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "healthy"})

    def test_status_endpoint_returns_project_name(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("status", body)
        self.assertIn("project", body)
        self.assertEqual(body["project"], "Student Task Manager")

    def test_metrics_endpoint_returns_prometheus_format(self):
        """After hitting an endpoint, /metrics must expose the counter."""
        self.client.get("/api/tasks")
        resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"demo_http_requests_total", resp.data)

    def test_metrics_content_type_is_prometheus(self):
        resp = self.client.get("/metrics")
        self.assertIn("text/plain", resp.content_type)

    def test_home_page_loads(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Student Task Manager", resp.data)


# ---------------------------------------------------------------------------
# 7. Full lifecycle integration test
# ---------------------------------------------------------------------------
class TestFullTaskLifecycle(BaseTaskTest):

    def test_create_complete_then_delete(self):
        """End-to-end: create → verify listed → complete → verify → delete → gone."""
        # Create
        create_resp = self.make_task(title="Full cycle task", priority="high")
        self.assertEqual(create_resp.status_code, 201)
        tid = create_resp.get_json()["id"]

        # Verify listed
        tasks = self.client.get("/api/tasks").get_json()
        self.assertTrue(any(t["id"] == tid for t in tasks))

        # Complete
        patch_resp = self.client.patch(f"/api/tasks/{tid}", json={"completed": True})
        self.assertTrue(patch_resp.get_json()["completed"])

        # Verify listed as completed
        tasks = self.client.get("/api/tasks").get_json()
        task = next(t for t in tasks if t["id"] == tid)
        self.assertTrue(task["completed"])

        # Delete
        del_resp = self.client.delete(f"/api/tasks/{tid}")
        self.assertEqual(del_resp.status_code, 204)

        # Verify gone
        tasks = self.client.get("/api/tasks").get_json()
        self.assertFalse(any(t["id"] == tid for t in tasks))

    def test_multiple_tasks_independent_state(self):
        """Completing one task must not affect another task's state."""
        id_a = self.task_id(title="Task A")
        id_b = self.task_id(title="Task B")

        self.client.patch(f"/api/tasks/{id_a}", json={"completed": True})

        tasks = {t["id"]: t for t in self.client.get("/api/tasks").get_json()}
        self.assertTrue(tasks[id_a]["completed"])
        self.assertFalse(tasks[id_b]["completed"])


if __name__ == "__main__":
    unittest.main()
