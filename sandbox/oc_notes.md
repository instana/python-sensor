# OpenShift CLI Reference Guide

Quick reference for OpenShift CLI commands for deploying Python applications with Instana monitoring.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Instana Agent Setup](#instana-agent-setup)
- [Instana Autotrace Webhook](#instana-autotrace-webhook)
- [Python Application Deployment](#python-application-deployment)
- [Application Updates](#application-updates)
- [Route Configuration](#route-configuration)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- OpenShift CLI (`oc`) installed
- Helm 3.x installed
- Docker/Podman for building images
- Valid Instana credentials (agent key and download key)
- Access to OpenShift cluster

---

## Initial Setup

### Login to OpenShift

```bash
oc login <host-address> -u <host-user> -p <host-password>
```

### Environment Variables

Set these variables before running commands:

```bash
# Application Configuration
export NS=namespace
export IMG=image-name
export ROUTE=route-name
export DEP=deployment-name
export SVC=service-name

# Instana Configuration
export AGENT_KEY=<agent-key>
export DOWNLOAD=<download-key>
export INSTANA_HOST=<host-address>
export CLUSTER_NAME=<cluster-name>
export ZONE_NAME=<zone-name>
```

---

## Instana Agent Setup

### Install/Upgrade Instana Agent

Use `install` for first-time setup or `upgrade` for updates:

```bash
helm upgrade instana-agent \
  --repo https://agents.instana.io/helm \
  --namespace instana-agent \
  --create-namespace \
  --set agent.key=$AGENT_KEY \
  --set agent.downloadKey=$DOWNLOAD \
  --set agent.endpointHost=$INSTANA_HOST \
  --set agent.endpointPort=443 \
  --set cluster.name=$CLUSTER_NAME \
  --set openshift.enabled=true \
  --set zone.name=$ZONE_NAME \
  instana-agent
```

### Force Delete Instana Agent (if stuck)

If the agent is not being deleted properly, remove finalizers:

```bash
oc patch instanaagent.instana.io instana-agent \
  -n instana-agent \
  -p '{"metadata":{"finalizers":[]}}' \
  --type=merge
```

---

## Instana Autotrace Webhook

### Install Autotrace Webhook

```bash
helm install instana-autotrace-webhook \
  --create-namespace \
  --namespace instana-autotrace-webhook \
  --repo https://agents.instana.io/helm \
  instana-autotrace-webhook \
  --set webhook.imagePullCredentials.password=$DOWNLOAD \
  --set openshift.enabled=true
```

---

## Python Application Deployment

### Create New Project

```bash
oc new-project $NS
oc project $NS
```

### Build and Deploy Application

Create internal image registry and build from source:

```bash
# Create build configuration
oc new-build --strategy=docker --binary=true --name=$IMG -n $NS

# Build image from current directory
oc start-build $IMG --from-dir=. --follow -n $NS

# Deploy the application
oc new-app $IMG:latest -n $NS

# Verify deployment and service
oc get deployment,svc -n $NS
```

### Create HTTPS Route

```bash
oc create route edge $ROUTE \
  --service=$IMG \
  --port=3000 \
  -n $NS

# Get route URL
oc get route $ROUTE -n $NS
```

### Rebuild After Code Changes

```bash
oc start-build $IMG --from-dir=. --follow
```

### Apply Deployment Changes

```bash
oc apply -f deployment.yaml -n $NS
```

---

## Application Updates

### Update Existing Application

Create build config if it doesn't exist:

```bash
oc new-build --strategy=docker --binary=true --name=$IMG -n $NS
```

Rebuild and deploy:

```bash
# Rebuild image
oc start-build $IMG --from-dir=. --follow -n $NS

# Trigger rolling update
oc rollout restart deployment/$DEP -n $NS
```

---

## Route Configuration

### Create HTTP Route

```bash
oc expose service $SVC --port=3000 -n $NS
```

### Create HTTPS Route (TLS Edge Termination)

```bash
oc create route edge $ROUTE \
  --service=$SVC \
  --port=3000 \
  -n $NS
```

---

## Troubleshooting

### Common Commands

```bash
# Check pod status
oc get pods -n $NS

# View pod logs
oc logs -f deployment/$DEP -n $NS

# Describe deployment
oc describe deployment $DEP -n $NS

# Check events
oc get events -n $NS --sort-by='.lastTimestamp'

# Access pod shell
oc rsh deployment/$DEP -n $NS

# Check build logs
oc logs -f bc/$IMG -n $NS

# List all resources
oc get all -n $NS

# Delete and recreate deployment
oc delete deployment $DEP -n $NS
oc new-app $IMG:latest -n $NS
```

### Instana Agent Status

```bash
# Check agent pods
oc get pods -n instana-agent

# View agent logs
oc logs -f daemonset/instana-agent -n instana-agent

# Check agent configuration
oc get configmap -n instana-agent
```

---

## Notes

- Default application port is set to `3000` - adjust as needed
- Use `helm upgrade` instead of `helm install` to update existing installations
- Always verify deployments with `oc get` commands after changes
- Routes created with `edge` termination handle TLS at the router level
