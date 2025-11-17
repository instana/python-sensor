# Kubernetes Deployment Guide

## Build Docker Images

Build the Flask application image:
```bash
docker build -f sandbox/Dockerfile -t flask-app:latest .
```

Build the Instana agent image:
```bash
docker build -f sandbox/Dockerfile.agent -t instana-agent:latest sandbox/
```

## Deploy to Kubernetes

Deploy the Instana agent:
```bash
kubectl apply -f sandbox/k8s/agent-deployment.yaml
```

Deploy the Flask application:
```bash
kubectl apply -f sandbox/k8s/deployment.yaml
```

## Update Deployments

If you make any changes to the code, restart the Instana agent deployment:
```bash
kubectl rollout restart deployment/instana-agent
```

If you make any changes to the code, restart the Flask app deployment:
```bash
kubectl rollout restart deployment/flask-app
```

Check the rollout status:
```bash
kubectl rollout status deployment/instana-agent
```

## Access the Application

Forward port 5000 to access the Flask app locally:
```bash
kubectl port-forward deployment/flask-app 5000:5000
```

## Monitor Pods

List all active pods:
```bash
kubectl get pods
```

## View Logs

View Flask app logs (replace `<flask_app-pod_name>` with actual pod name):
```bash
kubectl logs <flask_app-pod_name> -f
```

In a different terminal, view Instana agent logs (replace `<instana_agent-pod_name>` with actual pod name):
```bash
kubectl logs <instana_agent-pod_name> -f
```

## Test the Application

Open your browser and navigate to `http://localhost:5000` to see the application in action.

### Available Endpoints

- **`/`** - Home endpoint that returns basic application info and pod hostname
- **`/multiprocess`** - Multiprocessing endpoint that spawns 5 processes to make concurrent HTTP requests to google.com
  - **Note:** This endpoint requires higher resource limits due to multiprocessing
  - Current resource limits: 512Mi memory, 500m CPU

### Testing the Multiprocess Endpoint

```bash
curl http://localhost:5000/multiprocess
```

This will return a JSON response with results from 5 concurrent processes.


