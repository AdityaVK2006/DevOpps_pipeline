# College DevOps Pipeline Demo

A small end-to-end assignment showing Git collaboration, Jenkins CI/CD, Docker containers, Minikube deployment, and Prometheus/Grafana monitoring. The sample app is a student task manager with assignment tracking, a health check, and a Prometheus metrics endpoint.

## Pipeline

```text
Teammate branch → Git pull request/merge → Jenkins checkout → build image in Minikube
                                              → deploy app + monitoring → rollout check
```

Jenkins builds directly into Minikube's image store, so this classroom demo does not need a public container registry.

## Requirements

- Git
- Docker
- Minikube and `kubectl`
- Jenkins with a Pipeline job and permission to run `git`, `minikube`, and `kubectl`
- A Minikube cluster already started, and the Jenkins agent must use the same Minikube profile/context

Example local setup (install the tools separately for your operating system):

```sh
minikube start
kubectl get nodes
```

## Run the pipeline

1. Push this project to a Git hosting service such as GitHub/GitLab.
2. In Jenkins, create **New Item → Pipeline**.
3. Under Pipeline, choose **Pipeline script from SCM**, select Git, and enter the repository URL and branch (for example, `main`). Configure repository credentials if it is private.
4. Save and select **Build Now**. Jenkins checks out the selected revision, builds `devops-demo:latest` in Minikube, deploys the app, then deploys Prometheus and Grafana.

The Jenkins agent needs access to the Minikube cluster and Docker driver. If Jenkins itself runs in a container, configure access to the host's Minikube/kubeconfig deliberately; the simplest assignment setup is a Jenkins agent installed on the same machine as Minikube.

## Check the deployment

```sh
kubectl get pods,services -n devops-demo
kubectl port-forward -n devops-demo service/demo-app 5000:5000
```

Open `http://localhost:5000/` for the task manager. Add assignments with a course, due date, and priority; mark them complete, search/filter your list, or remove them. Tasks are stored in SQLite. Minikube mounts a persistent volume for the database, so task data survives an app pod restart. Also available: `http://localhost:5000/health` for the health check and `http://localhost:5000/metrics` for metrics.

In separate terminals, access the monitoring UIs:

```sh
kubectl port-forward -n devops-demo service/prometheus 9090:9090
kubectl port-forward -n devops-demo service/grafana 3000:3000
```

Open Prometheus at `http://localhost:9090` and Grafana at `http://localhost:3000` (demo login: `admin` / `admin`). Grafana's Prometheus data source is provisioned automatically. Try `up` or `demo_http_requests_total` in Prometheus/Grafana. Visit the app a few times to generate request metrics. Create a simple Grafana dashboard panel with `demo_http_requests_total` for a visible assignment demo.

## Git collaboration example

Each teammate should work on a separate branch and merge changes through a pull request:

```sh
git clone <repository-url>
cd <repository-folder>
git switch -c feature/update-message
# edit files
git add .
git commit -m "Update demo message"
git push -u origin feature/update-message
```

Open a pull request to `main`; a teammate reviews it, then merge it. Configure the Jenkins job to build `main` (or add a Git hosting webhook to trigger builds after merges).

## Project files

- `app.py`, `requirements.txt`: Flask app and metrics.
- `templates/`, `static/`: responsive student task manager UI.
- `Dockerfile`: container image definition.
- `Jenkinsfile`: build, deploy, and rollout stages.
- `k8s/`: namespace, app, Prometheus and Grafana Kubernetes resources.

---

## Enhanced Jenkins CI/CD Pipeline

> **Contribution by:** feature branch `feature/jenkins-testing-enhancements`

### What the original pipeline did

The original `Jenkinsfile` had four stages:

1. **Build application image** – `docker build` tagged with the Jenkins build number.
2. **Test application** – ran `python -m unittest discover` inside the built container.
3. **Load images into Minikube** – pulled Prometheus and Grafana images and loaded all three into Minikube.
4. **Deploy to Minikube** – applied Kubernetes manifests and waited for rollouts of the app, Prometheus, and Grafana.

### Updated pipeline flow

```
Git Checkout
      │
      ▼
Code Quality Checks  ← NEW: Ruff linting (fails fast before any build)
      │
      ▼
Build application image
      │
      ▼
Unit Tests & Reporting  ← IMPROVED: JUnit XML report published to Jenkins
      │
      ▼
Load images into Minikube
      │
      ▼
Deploy application  ← split from monitoring for clarity
      │
      ▼
Deploy monitoring components
      │
      ▼
Post-Deployment Smoke Tests  ← NEW: live HTTP checks against deployed app
      │
      ▼
Pipeline Result
```

### Why the code-quality stage was introduced

Linting catches common bugs and style inconsistencies before the image is built, saving build time. [Ruff](https://docs.astral.sh/ruff/) was chosen because it:

- Is extremely fast (written in Rust).
- Replaces flake8, isort, and pyupgrade in a single tool.
- Is configured once in `pyproject.toml` and can be used both locally and in CI without additional infrastructure.

Ruff runs **on the Jenkins agent** (not inside Docker) using an isolated virtual environment created from `requirements-dev.txt`. This keeps production image dependencies clean.

### How automated unit tests are executed

Tests run inside the freshly-built Docker container so the test environment exactly matches the deployed environment:

```sh
docker run --rm \
    -v "$WORKSPACE/tests:/tests:ro" \
    -v "$WORKSPACE/test-reports:/test-reports" \
    "$APP_IMAGE" \
    sh -c "pip install --quiet unittest-xml-reporting==3.2.0 && \
           python -m xmlrunner discover -s /tests -o /test-reports --verbosity 2"
```

The test suite (`tests/test_app.py`) was expanded from 6 tests to over 35, covering:

| Area | Tests added |
|---|---|
| Health & status endpoints | HTTP 200, response body assertions |
| Task creation (happy path) | All fields, optional fields, whitespace trimming, unique IDs |
| Task creation (validation) | Empty title, whitespace title, missing title key, bad priority, bad date, oversized fields, non-JSON body |
| Task listing | Empty DB, count, JSON array type, field presence, ordering |
| PATCH / completion | Mark complete, mark incomplete, 404, 400 on missing field, 400 on string boolean |
| DELETE | 204 + no body, 404, only targeted task removed |
| Data isolation | Failed validation must not create partial tasks |
| Full lifecycle | Create → list → complete → verify → delete → gone |
| Metrics | Content, content-type |

### How Jenkins publishes test results

`unittest-xml-reporting` (`xmlrunner`) generates JUnit-compatible XML into the `test-reports/` directory on the workspace. The `junit` step in the `post { always { … } }` block publishes this report through the Jenkins JUnit plugin.

**Required Jenkins plugin:** [JUnit Plugin](https://plugins.jenkins.io/junit/)  
Install via: *Manage Jenkins → Plugins → Available plugins → search "JUnit"*

After each build, click **Test Results** in the build sidebar to see a breakdown of passing and failing tests.

### What the smoke tests verify

`scripts/smoke_test.sh` runs after the application deployment has passed its rollout check. It:

1. Resolves the Minikube NodePort URL automatically (`minikube ip` + port `30000`).
2. Waits up to 150 s for the application to become reachable (bounded retry loop, no arbitrary `sleep`).
3. Asserts the following endpoints:

| Endpoint | Check |
|---|---|
| `/health` | HTTP 200, body contains `healthy` |
| `/api/status` | HTTP 200, body contains `running` and `Student Task Manager` |
| `/api/tasks` | HTTP 200, body is a JSON array |
| `/metrics` | HTTP 200, body contains `demo_http_requests_total` |
| `/` | HTTP 200, body contains `Student Task Manager` |

No destructive requests (POST / PATCH / DELETE) are made. No credentials are logged.

### How failures affect the pipeline

| Failure point | Effect |
|---|---|
| Ruff lint error | Pipeline fails in **Code Quality Checks**; image is not built |
| Unit test failure | Pipeline fails in **Unit Tests & Reporting**; deployment is not attempted |
| Kubernetes rollout timeout | Pipeline fails in **Deploy application** or **Deploy monitoring** |
| Smoke test assertion failure | Pipeline fails in **Post-Deployment Smoke Tests**; clear diagnostic printed |

### Running tests locally

**Run the unit tests:**

```sh
# Install runtime dependencies (if not already installed)
pip install -r requirements.txt

# Run tests
python -m unittest discover -s tests -v
```

**Run Ruff locally:**

```sh
pip install -r requirements-dev.txt
ruff check app.py tests/
```

**Run the smoke tests locally** (requires a running Minikube cluster):

```sh
# Option 1: let the script resolve Minikube IP automatically
bash scripts/smoke_test.sh

# Option 2: supply a URL manually (e.g. after a port-forward)
bash scripts/smoke_test.sh http://localhost:5000
```

### Troubleshooting common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `ruff: command not found` in Code Quality stage | `requirements-dev.txt` not installed or venv broken | Ensure Python 3 is on the agent PATH; check the venv creation step |
| `xmlrunner` import error in test stage | The pip install inside the container failed | Verify internet access from Docker; check the container logs |
| JUnit report not found | `test-reports/*.xml` path mismatch | Ensure `mkdir -p` in the Test stage ran and the container wrote to `/test-reports` |
| Smoke tests time out | App not reachable via NodePort | Run `kubectl get svc -n devops-demo` and `minikube ip`; verify nodePort 30000 is open |
| Smoke test 000 HTTP code | `curl` not on PATH in the agent shell | Install `curl` on the Jenkins agent OS |
| `minikube ip` returns empty | Minikube not started or wrong profile | Run `minikube start` before triggering the build |

### Inspecting test reports

After a pipeline run, open the Jenkins build page and click **Test Results** in the left sidebar. You will see:

- Total tests run / passed / failed / skipped.
- Per-test pass/fail with error messages and stack traces for failures.
- Historical trend graph (requires multiple builds).
