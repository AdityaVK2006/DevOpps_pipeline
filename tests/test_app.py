import tempfile
import unittest
from pathlib import Path

import app as student_app


class StudentTaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.database_dir = tempfile.TemporaryDirectory()
        student_app.DATABASE = Path(self.database_dir.name) / "tasks.db"
        student_app.init_db()
        student_app.app.config.update(TESTING=True)
        self.client = student_app.app.test_client()

    def tearDown(self):
        self.database_dir.cleanup()

    def create_task(self, **overrides):
        task = {
            "title": "Read chapter 4",
            "course": "Biology",
            "due_date": "2026-11-01",
            "priority": "high",
        }
        task.update(overrides)
        return self.client.post("/api/tasks", json=task)

    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Task Manager", response.data)

    def test_health_and_status_endpoints(self):
        health = self.client.get("/health")
        status = self.client.get("/api/status")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json(), {"status": "healthy"})
        self.assertEqual(status.get_json()["status"], "running")

    def test_create_and_list_tasks(self):
        created = self.create_task()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["title"], "Read chapter 4")
        self.assertEqual(created.get_json()["priority"], "high")

        listed = self.client.get("/api/tasks")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.get_json()), 1)
        self.assertEqual(listed.get_json()[0]["course"], "Biology")

    def test_create_rejects_missing_title(self):
        response = self.client.post("/api/tasks", json={"title": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_create_rejects_invalid_priority_and_due_date(self):
        bad_priority = self.create_task(priority="urgent")
        bad_date = self.create_task(due_date="not-a-date")

        self.assertEqual(bad_priority.status_code, 400)
        self.assertEqual(bad_date.status_code, 400)

    def test_task_can_be_completed_and_deleted(self):
        task_id = self.create_task().get_json()["id"]

        completed = self.client.patch(
            f"/api/tasks/{task_id}", json={"completed": True}
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.get_json()["completed"])

        deleted = self.client.delete(f"/api/tasks/{task_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])

    def test_metrics_endpoint_exposes_prometheus_metrics(self):
        self.client.get("/api/status")

        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"demo_http_requests_total", response.data)


if __name__ == "__main__":
    unittest.main()
