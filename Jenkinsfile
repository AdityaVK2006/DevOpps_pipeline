// ============================================================
// Jenkinsfile – Student Task Manager CI/CD Pipeline
// ============================================================
//
// Stage order:
//   1. Code Quality Checks      – Ruff linting (runs on the Jenkins agent)
//   2. Build application image  – docker build -t devops-demo:<BUILD_NUMBER>
//   3. Unit Tests & Reporting   – unittest inside the app container, JUnit XML
//   4. Load images into Minikube
//   5. Deploy application       – kubectl apply + rollout check
//   6. Deploy monitoring        – Prometheus + Grafana rollout check
//   7. Post-Deployment Smoke Tests – HTTP checks via Minikube NodePort
//
// Requirements for the Jenkins agent:
//   - Git, Docker CLI + daemon
//   - Minikube (started, same profile/context as kubectl)
//   - kubectl configured with the correct kubeconfig / context
//   - Python 3 available on PATH (for the Code Quality stage)
//   - The JUnit plugin installed in Jenkins (for test-report publication)
//
// Required Jenkins plugin:
//   - JUnit Plugin (https://plugins.jenkins.io/junit/)
//     Publishes the XML test report and marks the build failed when tests fail.
// ============================================================

pipeline {
    agent any

    environment {
        APP_IMAGE        = "devops-demo:${BUILD_NUMBER}"
        PROMETHEUS_IMAGE = 'prom/prometheus:v3.5.0'
        GRAFANA_IMAGE    = 'grafana/grafana:12.1.1'
        K8S_NAMESPACE    = 'devops-demo'
        // Directory inside the container where test XML reports are written.
        TEST_REPORT_DIR  = 'test-reports'
    }

    stages {

        // ──────────────────────────────────────────────────────────────
        // Stage 1: Code Quality Checks
        // Runs Ruff on the workspace source and test files.
        // Executed directly on the Jenkins agent (not inside Docker) so
        // that linting can fail fast before any image is built.
        // ──────────────────────────────────────────────────────────────
        stage('Code Quality Checks') {
            steps {
                sh '''
                    # Install dev tools into an isolated virtual environment
                    # so they do not pollute the agent's global Python.
                    python3 -m venv .lint-venv
                    .lint-venv/bin/pip install --quiet -r requirements-dev.txt

                    echo "──────────────────────────────────────────"
                    echo "Running Ruff linter..."
                    echo "──────────────────────────────────────────"
                    .lint-venv/bin/ruff check app.py tests/

                    echo "Ruff: all checks passed."
                '''
            }
            post {
                always {
                    // Remove the venv to keep the workspace clean.
                    sh 'rm -rf .lint-venv || true'
                }
                failure {
                    echo 'Code Quality stage failed. Fix the linting issues reported above before rebuilding.'
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 2: Build application image
        // ──────────────────────────────────────────────────────────────
        stage('Build application image') {
            steps {
                sh '''
                    docker build -t "$APP_IMAGE" .
                '''
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 3: Unit Tests & Reporting
        // Runs tests inside the freshly-built container.
        // unittest-xml-reporting (xmlrunner) is installed inside the
        // container via requirements-dev.txt so that Jenkins can
        // consume the JUnit XML produced by the run.
        //
        // The test results XML is written to $WORKSPACE/test-reports/
        // and published by the JUnit plugin.
        //
        // A non-zero exit from the container causes the stage to fail.
        // ──────────────────────────────────────────────────────────────
        stage('Unit Tests & Reporting') {
            steps {
                // Ensure the report directory exists on the host workspace.
                sh 'mkdir -p "$WORKSPACE/$TEST_REPORT_DIR"'

                sh '''
                    docker run --rm \
                        -v "$WORKSPACE/tests:/tests:ro" \
                        -v "$WORKSPACE/$TEST_REPORT_DIR:/test-reports" \
                        "$APP_IMAGE" \
                        sh -c "
                            pip install --quiet unittest-xml-reporting==3.2.0 && \
                            python -m xmlrunner discover \
                                -s /tests \
                                -o /test-reports \
                                --verbosity 2
                        "
                '''
            }
            post {
                always {
                    // Publish the JUnit XML report regardless of pass/fail.
                    // Requires the Jenkins JUnit plugin to be installed.
                    junit allowEmptyResults: false,
                          testResults: "${TEST_REPORT_DIR}/*.xml"

                    echo 'Test report published. Check the "Test Results" tab in this build.'
                }
                failure {
                    echo 'Unit tests FAILED. Review the JUnit report above and fix failing tests before proceeding.'
                }
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 4: Load images into Minikube
        // ──────────────────────────────────────────────────────────────
        stage('Load images into Minikube') {
            steps {
                sh '''
                    docker pull "$PROMETHEUS_IMAGE"
                    docker pull "$GRAFANA_IMAGE"
                    minikube image load "$APP_IMAGE"
                    minikube image load "$PROMETHEUS_IMAGE"
                    minikube image load "$GRAFANA_IMAGE"
                '''
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 5: Deploy application
        // Apply the namespace + app manifest, then wait for rollout.
        // ──────────────────────────────────────────────────────────────
        stage('Deploy application') {
            steps {
                sh '''
                    kubectl apply -f k8s/namespace.yaml
                    sed "s|devops-demo:latest|$APP_IMAGE|g" k8s/app.yaml \
                        | kubectl apply -n "$K8S_NAMESPACE" -f -
                    kubectl rollout status \
                        -n "$K8S_NAMESPACE" \
                        deployment/demo-app \
                        --timeout=120s
                '''
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 6: Deploy monitoring components
        // Prometheus and Grafana are deployed after the app is healthy.
        // ──────────────────────────────────────────────────────────────
        stage('Deploy monitoring') {
            steps {
                sh '''
                    kubectl apply -n "$K8S_NAMESPACE" -f k8s/monitoring.yaml
                    kubectl rollout status \
                        -n "$K8S_NAMESPACE" \
                        deployment/prometheus \
                        --timeout=120s
                    kubectl rollout status \
                        -n "$K8S_NAMESPACE" \
                        deployment/grafana \
                        --timeout=120s
                '''
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Stage 7: Post-Deployment Smoke Tests
        // HTTP checks against the live Minikube NodePort (30000).
        // The smoke_test.sh script resolves the Minikube IP automatically.
        // It uses a bounded retry loop so it waits for the app to warm up
        // rather than relying on arbitrary sleep commands.
        // ──────────────────────────────────────────────────────────────
        stage('Post-Deployment Smoke Tests') {
            steps {
                sh '''
                    chmod +x scripts/smoke_test.sh
                    bash scripts/smoke_test.sh
                '''
            }
            post {
                failure {
                    echo 'Smoke tests FAILED. The application may not be responding correctly after deployment.'
                    echo 'Check: kubectl get pods,services -n devops-demo'
                    echo 'Check: kubectl logs -n devops-demo deployment/demo-app'
                }
            }
        }

    }

    // ──────────────────────────────────────────────────────────────────
    // Post-pipeline actions
    // ──────────────────────────────────────────────────────────────────
    post {
        success {
            echo '════════════════════════════════════════════════════'
            echo 'Pipeline completed successfully.'
            echo 'App   : http://<minikube-ip>:30000'
            echo 'Health: http://<minikube-ip>:30000/health'
            echo '════════════════════════════════════════════════════'
        }
        failure {
            echo 'Pipeline FAILED. Review the stage logs and the JUnit report above.'
        }
        always {
            echo "Build #${BUILD_NUMBER} finished with status: ${currentBuild.currentResult}"
        }
    }
}
