# College DevOps Pipeline Demo

A small end-to-end assignment showing Git collaboration, Jenkins CI/CD, Docker containers, Minikube deployment, and Prometheus/Grafana monitoring. The sample app is a Flask service with a health check and Prometheus metrics endpoint.

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

Open `http://localhost:5000/` for the app, `http://localhost:5000/health` for its health check, and `http://localhost:5000/metrics` for metrics.

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
- `Dockerfile`: container image definition.
- `Jenkinsfile`: build, deploy, and rollout stages.
- `k8s/`: namespace, app, Prometheus and Grafana Kubernetes resources.
