# Flask Instana Tracing Demo

Simple Flask app deployed on OpenShift to verify that `AUTOWRAPT_BOOTSTRAP=instana`
produces spans in the Instana UI — no `import instana` in application code.

## Prerequisites

- `oc` CLI logged in to the target OpenShift cluster
- `helm` 3.x installed
- Instana agent key + download key
- Instana backend host (e.g. `ingress-magenta-saas.instana.rocks`)

## Deploy

```bash
export AGENT_KEY="<instana-agent-key>"
export DOWNLOAD_KEY="<instana-download-key>"
export INSTANA_HOST="ingress-magenta-saas.instana.rocks"
export NS="python-tracer"          # optional, default: python-tracer

bash sandbox/flask-tracing-app/deploy.sh
```

The script:
1. Installs the Instana agent via Helm (skips if already running)
2. Builds the Flask image inside the cluster via `oc start-build` (no Docker Hub)
3. Deploys the app and creates an edge Route

## Test

```bash
oc port-forward svc/flask-tracing-demo 5000:5000 -n python-tracer &

curl http://localhost:5000/             # entry span
curl http://localhost:5000/hello/world  # named span
curl http://localhost:5000/slow         # 1 s latency span
curl http://localhost:5000/error        # error span
```

Check the Instana UI → **Services** → `flask-tracing-demo`.
Spans appear within ~30 s of the first request.

## Verify instrumentation

```bash
POD=$(oc get pod -n python-tracer -l app=flask-tracing-demo -o jsonpath='{.items[0].metadata.name}')
oc exec -n python-tracer $POD -- env | grep -E 'AUTOWRAPT|INSTANA'
```

`AUTOWRAPT_BOOTSTRAP=instana` must be present. No autotrace webhook is needed.

## Tear down

```bash
oc delete -f sandbox/flask-tracing-app/k8s/02-flask-app.yaml -n python-tracer
oc delete bc/flask-tracing-demo -n python-tracer
oc delete route/flask-tracing-demo -n python-tracer
```
