#!/usr/bin/env bash
# (c) Copyright IBM Corp. 2025
# =============================================================================
# deploy.sh -- Flask Instana Tracing Demo
#
# Same approach as deploy_real.sh:
#   - Uses OpenShift internal registry (no Docker Hub)
#   - Builds the image inside the cluster via oc new-build + oc start-build
#   - Installs / upgrades the Instana agent via Helm
#
# Usage:
#   export AGENT_KEY="<instana-agent-key>"
#   export DOWNLOAD_KEY="<instana-download-key>"
#   export INSTANA_HOST="ingress-magenta-saas.instana.rocks"
#   export NS="python-tracer"   # optional (default: python-tracer)
#   bash sandbox/flask-tracing-app/deploy.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -- Configuration -------------------------------------------------------------
NS="${NS:-python-tracer}"
APP_IMG="flask-tracing-demo"
REGISTRY="image-registry.openshift-image-registry.svc:5000/${NS}"

: "${AGENT_KEY:?    AGENT_KEY env var is not set}"
: "${DOWNLOAD_KEY:? DOWNLOAD_KEY env var is not set}"
: "${INSTANA_HOST:? INSTANA_HOST env var is not set}"

INSTANA_PORT="${INSTANA_PORT:-443}"
CLUSTER_NAME="${CLUSTER_NAME:-flask-demo-cluster}"
ZONE_NAME="${ZONE_NAME:-flask-demo-zone}"

# -- Color helpers -------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass()   { echo -e "${GREEN}[OK]  $*${NC}"; }
fail()   { echo -e "${RED}[ERR] $*${NC}"; exit 1; }
info()   { echo -e "${YELLOW}[i]   $*${NC}"; }
step()   { echo -e "${CYAN}[>>]  $*${NC}"; }
banner() {
    echo ""
    echo -e "${BOLD}=================================================${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}=================================================${NC}"
}

# -- Pre-flight checks ---------------------------------------------------------
banner "PRE-FLIGHT CHECKS"

command -v oc   &>/dev/null || fail "oc CLI not found."
command -v helm &>/dev/null || fail "helm not found."

step "Checking oc login status..."
oc whoami &>/dev/null || fail "Not logged in to OpenShift. Run 'oc login <host>' first."
pass "Logged in as: $(oc whoami)"

# -- Namespace -----------------------------------------------------------------
banner "NAMESPACE: $NS"
if ! oc get namespace "$NS" &>/dev/null; then
    oc new-project "$NS"
    pass "Namespace created: $NS"
else
    oc project "$NS"
    pass "Namespace ready: $NS"
fi

step "Granting anyuid SCC to default ServiceAccount..."
oc adm policy add-scc-to-user anyuid \
    "system:serviceaccount:${NS}:default" 2>&1 \
    && pass "anyuid SCC granted" \
    || info "Could not grant anyuid SCC -- continuing"

# -- Instana Agent (Helm) ------------------------------------------------------
banner "INSTANA AGENT"

if helm list -n instana-agent -q 2>/dev/null | grep -q "^instana-agent$"; then
    pass "Instana agent is already running"
else
    info "Installing Instana agent..."
    helm upgrade --install instana-agent \
        --repo https://agents.instana.io/helm \
        --namespace instana-agent \
        --create-namespace \
        --set agent.key="$AGENT_KEY" \
        --set agent.downloadKey="$DOWNLOAD_KEY" \
        --set agent.endpointHost="$INSTANA_HOST" \
        --set agent.endpointPort="$INSTANA_PORT" \
        --set cluster.name="$CLUSTER_NAME" \
        --set openshift.enabled=true \
        --set zone.name="$ZONE_NAME" \
        instana-agent
    oc adm policy add-scc-to-user privileged -z instana-agent -n instana-agent || true
    pass "Instana agent installed"
fi

# -- Flask image -- build via OpenShift internal registry ----------------------
banner "FLASK IMAGE BUILD"

step "Checking BuildConfig..."
if ! oc get bc "$APP_IMG" -n "$NS" &>/dev/null; then
    oc new-build --strategy=docker --binary=true --name="$APP_IMG" -n "$NS"
    pass "BuildConfig created: $APP_IMG"
else
    info "BuildConfig already exists: $APP_IMG"
fi

step "Starting build (source: $SCRIPT_DIR)..."
oc start-build "$APP_IMG" --from-dir="$SCRIPT_DIR" --follow -n "$NS"
pass "Flask image built: ${REGISTRY}/${APP_IMG}:latest"

# -- Apply manifests -----------------------------------------------------------
banner "APPLY MANIFESTS"

step "Applying k8s/02-flask-app.yaml..."
oc apply -f k8s/02-flask-app.yaml -n "$NS"
pass "Service and Deployment applied"

step "Linking internal registry image to Deployment..."
oc set image deployment/"$APP_IMG" \
    "${APP_IMG}=${REGISTRY}/${APP_IMG}:latest" \
    -n "$NS"
pass "Image set: ${REGISTRY}/${APP_IMG}:latest"

# -- Wait for rollout ----------------------------------------------------------
banner "WAITING FOR DEPLOYMENT"

step "Waiting for: deployment/${APP_IMG}..."
if oc rollout status deployment/"$APP_IMG" -n "$NS" --timeout=180s; then
    pass "$APP_IMG is ready"
else
    fail "$APP_IMG did not become ready within 180s. Logs: oc logs -f deployment/$APP_IMG -n $NS"
fi

# -- Route ---------------------------------------------------------------------
banner "ROUTE"

if ! oc get route "$APP_IMG" -n "$NS" &>/dev/null; then
    step "Creating route..."
    oc create route edge "$APP_IMG" \
        --service="$APP_IMG" \
        --port=5000 \
        -n "$NS"
    pass "Route created"
fi

ROUTE_HOST=$(oc get route "$APP_IMG" -n "$NS" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

# -- Summary -------------------------------------------------------------------
banner "SUMMARY"

oc get pods -n "$NS" -l app="$APP_IMG"
echo ""

if [ -n "$ROUTE_HOST" ]; then
    pass "Application URL: https://${ROUTE_HOST}"
fi

info "Verify env vars -- should see AUTOWRAPT_BOOTSTRAP:"
echo "  POD=\$(oc get pod -n $NS -l app=$APP_IMG -o jsonpath='{.items[0].metadata.name}')"
echo "  oc exec -n $NS \$POD -- env | grep -E 'AUTOWRAPT|INSTANA'"
echo ""
info "Send test requests:"
echo "  oc port-forward svc/$APP_IMG 5000:5000 -n $NS &"
echo "  curl http://localhost:5000/"
echo "  curl http://localhost:5000/hello/world"
echo "  curl http://localhost:5000/slow"
echo "  curl http://localhost:5000/error"
echo ""
info "To tear down the stack:"
echo "  oc delete -f k8s/02-flask-app.yaml -n $NS"
echo "  oc delete bc/$APP_IMG              -n $NS"
echo "  oc delete route/$APP_IMG           -n $NS"
echo ""
info "To tail logs:"
echo "  oc logs -f deployment/$APP_IMG -n $NS"
echo ""

# Made with Bob
