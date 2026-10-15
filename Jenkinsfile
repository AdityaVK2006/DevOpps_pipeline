pipeline {
    agent any

    environment {
        APP_IMAGE = 'devops-demo:latest'
        PROMETHEUS_IMAGE = 'prom/prometheus:v3.5.0'
        GRAFANA_IMAGE = 'grafana/grafana:12.1.1'
        K8S_NAMESPACE = 'devops-demo'
    }

    stages {
        stage('Build and load images') {
            steps {
                sh '''
                    docker build -t "$APP_IMAGE" .
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
                    kubectl apply -n "$K8S_NAMESPACE" -f k8s/app.yaml
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
