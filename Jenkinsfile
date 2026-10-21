pipeline {
    agent any

    environment {
        APP_IMAGE = "devops-demo:${BUILD_NUMBER}"
        PROMETHEUS_IMAGE = 'prom/prometheus:v3.5.0'
        GRAFANA_IMAGE = 'grafana/grafana:12.1.1'
        K8S_NAMESPACE = 'devops-demo'
    }

    stages {
        stage('Build application image') {
            steps {
                sh '''
                    docker build -t "$APP_IMAGE" .
                '''
            }
        }
        stage('Test application') {
            steps {
                sh '''
                    docker run --rm \
                        -v "$WORKSPACE/tests:/tests:ro" \
                        "$APP_IMAGE" \
                        python -m unittest discover -s /tests -v
                '''
            }
        }
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
        stage('Deploy to Minikube') {
            steps {
                sh '''
                    kubectl apply -f k8s/namespace.yaml
                    sed "s|devops-demo:latest|$APP_IMAGE|g" k8s/app.yaml | kubectl apply -n "$K8S_NAMESPACE" -f -
                    kubectl rollout status -n "$K8S_NAMESPACE" deployment/demo-app --timeout=120s
                    kubectl apply -n "$K8S_NAMESPACE" -f k8s/monitoring.yaml
                    kubectl rollout status -n "$K8S_NAMESPACE" deployment/prometheus --timeout=120s
                    kubectl rollout status -n "$K8S_NAMESPACE" deployment/grafana --timeout=120s
                '''
            }
        }
    }
    post {
        success { echo 'Deployment completed successfully.' }
        failure { echo 'Pipeline failed. Check the stage logs above.' }
    }
}
