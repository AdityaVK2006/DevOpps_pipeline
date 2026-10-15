pipeline {
    agent any

    environment {
        APP_IMAGE = 'devops-demo:latest'
        K8S_NAMESPACE = 'devops-demo'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Build image in Minikube') {
            steps {
                sh '''
                    docker build -t "$APP_IMAGE" .
                    minikube image load "$APP_IMAGE"
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
