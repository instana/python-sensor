#!/usr/bin/env bash
# (c) Copyright IBM Corp. 2025
# deploy.sh — LiteLLM + Instana autotrace webhook (latest version) test environment
#
# The autotrace webhook is always installed at the latest version from the helm
# repo (no --version flag). No manual code changes are needed; the webhook
# injects the sensor automatically via PYTHONPATH.
#
# Usage:
#   export NS=python-tracer        # optional, default: python-tracer
#   export AGENT_KEY=<key>         # Instana agent key
#   export DOWNLOAD_KEY=<key>      # containers.instana.io download key
#   export INSTANA_HOST=<host>     # Instana backend host
#   ./sandbox/litellm-with-k8s/deploy.sh
#
# Prerequisites:
#   - oc login must be completed
#   - helm 3.x must be installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Configuration ─────────────────────────────────────────────────────────────
NS="${NS:-python-tracer}"
APP="litellm-proxy"
REGISTRY="image-registry.openshift-image-registry.svc:5000/${NS}"

AGENT_KEY="${AGENT_KEY:-n399JZhWQtuwd6pB42oukg}"
DOWNLOAD_KEY="${DOWNLOAD_KEY:-IYUKKimCQ-6qVTawqCHPEw}"
INSTANA_HOST="${INSTANA_HOST:-ingress-magenta-saas.instana.rocks}"
CLUSTER_NAME="${CLUSTER_NAME:-owi-csp-cluster}"
ZONE_NAME="${ZONE_NAME:-owi-csp-zone}"

WEBHOOK_NS="instana-autotrace-webhook"
WEBHOOK_REGISTRY="containers.instana.io"
WEBHOOK_REGISTRY_USER="_"

# ── Colour constants ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

pass()   { echo -e "${GREEN}✅  $*${NC}"; }
fail()   { echo -e "${RED}❌  $*${NC}"; exit 1; }
info()   { echo -e "${YELLOW}ℹ️   $*${NC}"; }
step()   { echo -e "${CYAN}▶   $*${NC}"; }
banner() {
    echo ""
    echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
}

# ── Pre-flight checks ─────────────────────────────────────────────────────────
banner "PRE-FLIGHT CHECKS"

command -v oc   &>/dev/null || fail "oc CLI not found."
command -v helm &>/dev/null || fail "helm not found."

step "Checking oc login..."
oc whoami &>/dev/null || fail "Not logged in to OpenShift. Run 'oc login <host>'."
pass "Logged in as: $(oc whoami)"

# ── Namespace ─────────────────────────────────────────────────────────────────
banner "NAMESPACE"

step "Namespace: $NS"
if ! oc get namespace "$NS" &>/dev/null; then
    oc new-project "$NS"
else
    oc project "$NS"
fi
pass "Namespace ready: $NS"

oc adm policy add-scc-to-user anyuid \
    "system:serviceaccount:${NS}:default" 2>&1 && pass "anyuid SCC granted" \
    || info "anyuid SCC could not be granted — continuing"

# ── Autotrace Webhook (latest version) ───────────────────────────────────────
banner "AUTOTRACE WEBHOOK — LATEST VERSION"
echo ""
echo -e "  ${CYAN}Installing latest version from helm repo (no --version flag).${NC}"
echo ""

step "Adding / updating instana helm repo..."
helm repo add instana https://agents.instana.io/helm 2>/dev/null || true
helm repo update
pass "Helm repo up to date"

step "Removing existing webhook (if any)..."
helm uninstall instana-autotrace-webhook -n "$WEBHOOK_NS" 2>/dev/null \
    && info "Old webhook removed" \
    || info "Webhook was not installed"

step "Installing autotrace webhook (latest version)..."
helm upgrade --install instana-autotrace-webhook \
    instana/instana-autotrace-webhook \
    --create-namespace \
    --namespace "$WEBHOOK_NS" \
    --set openshift.enabled=true \
    --set webhook.imagePullCredentials.registry="$WEBHOOK_REGISTRY" \
    --set webhook.imagePullCredentials.username="$WEBHOOK_REGISTRY_USER" \
    --set webhook.imagePullCredentials.password="$DOWNLOAD_KEY" \
    --wait --timeout=120s
WEBHOOK_VER=$(helm list -n "$WEBHOOK_NS" -o json \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(r[0]['chart'] if r else 'unknown')" 2>/dev/null || echo "unknown")
pass "Autotrace webhook installed: $WEBHOOK_VER"

# ── Instana Agent ─────────────────────────────────────────────────────────────
banner "INSTANA AGENT"

step "Checking Instana agent..."
if helm list -n instana-agent -q 2>/dev/null | grep -q "^instana-agent$"; then
    pass "Instana agent already running"
else
    info "Installing Instana agent..."
    helm upgrade --install instana-agent \
        instana/instana-agent \
        --namespace instana-agent \
        --create-namespace \
        --set agent.key="$AGENT_KEY" \
        --set agent.downloadKey="$DOWNLOAD_KEY" \
        --set agent.endpointHost="$INSTANA_HOST" \
        --set agent.endpointPort=443 \
        --set cluster.name="$CLUSTER_NAME" \
        --set openshift.enabled=true \
        --set zone.name="$ZONE_NAME" \
        --wait --timeout=300s
    oc adm policy add-scc-to-user privileged -z instana-agent -n instana-agent || true
    pass "Instana agent installed"
fi

# ── Build LiteLLM image ───────────────────────────────────────────────────────
banner "IMAGE BUILD"

step "Checking BuildConfig..."
if ! oc get bc "$APP" -n "$NS" &>/dev/null; then
    oc new-build --strategy=docker --binary=true --name="$APP" -n "$NS"
    pass "BuildConfig created: $APP"
else
    info "BuildConfig already exists: $APP"
fi

step "Starting build (Dockerfile + app.py + requirements.txt)..."
oc start-build "$APP" --from-dir="$SCRIPT_DIR" --follow -n "$NS"
pass "Image built: ${REGISTRY}/${APP}:latest"

# ── Apply manifests ───────────────────────────────────────────────────────────
banner "APPLY MANIFESTS"

step "Applying k8s/deployment.yaml..."
oc apply -f "$SCRIPT_DIR/k8s/deployment.yaml" -n "$NS"
pass "Manifests applied"

step "Setting image on deployment..."
oc set image deployment/"$APP" \
    "${APP}=${REGISTRY}/${APP}:latest" \
    -n "$NS"
pass "Image set"

# ── Wait for rollout ──────────────────────────────────────────────────────────
banner "WAITING FOR DEPLOYMENT"

step "Waiting for: deployment/${APP}..."
if oc rollout status deployment/"$APP" -n "$NS" --timeout=300s; then
    pass "$APP is ready"
else
    fail "$APP did not become ready within 300s. Logs: oc logs -f deployment/$APP -n $NS"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
banner "READY"

ROUTE_HOST=$(oc get route "$APP" -n "$NS" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -z "$ROUTE_HOST" ]]; then
    info "Route not ready yet — retry in a few seconds:"
    info "  oc get route $APP -n $NS"
    ROUTE_HOST="<route-host>"
fi

echo ""
echo -e "${BOLD}Application URL:  https://${ROUTE_HOST}${NC}"
echo ""
echo "  Test endpoints:"
echo ""
echo "  # Health check"
echo "    curl -sk https://${ROUTE_HOST}/health | python3 -m json.tool"
echo ""
echo "  # Model list"
echo "    curl -sk https://${ROUTE_HOST}/models | python3 -m json.tool"
echo ""
echo "  # Chat completions (LiteLLM -> fake-openai)"
echo "    curl -sk -X POST https://${ROUTE_HOST}/chat/completions \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -d '{\"model\":\"fake-gpt-4\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}' \\"
echo "         | python3 -m json.tool"
echo ""
echo "  # Slow endpoint (1s delay — observe trace duration)"
echo "    curl -sk https://${ROUTE_HOST}/slow | python3 -m json.tool"
echo ""
echo "  Verify autotrace injection:"
echo "    oc logs -f deployment/${APP} -n ${NS} | head -30"
echo "    # First lines should mention 'instana' or show sensor output"
echo ""
echo "  Check in Instana UI:"
echo "    Analytics -> Calls -> Service: litellm-proxy"
echo "    litellm -> fake-openai trace chain should be complete"
echo ""
info "To remove resources:"
echo "  oc delete -f $SCRIPT_DIR/k8s/deployment.yaml -n $NS"
echo "  oc delete bc/$APP -n $NS"
echo ""
info "To remove the webhook:"
echo "  helm uninstall instana-autotrace-webhook -n $WEBHOOK_NS"

# Made with Bob
