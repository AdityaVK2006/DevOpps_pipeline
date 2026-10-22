#!/usr/bin/env bash
# smoke_test.sh – Post-deployment HTTP smoke tests for the Student Task Manager.
#
# Usage:
#   bash scripts/smoke_test.sh [APP_URL]
#
# If APP_URL is not supplied, the script resolves the application URL using
# Minikube's NodePort (nodePort: 30000 as defined in k8s/app.yaml).
#
# The script:
#   1. Waits for the application to become reachable (bounded retry loop).
#   2. Verifies each critical endpoint returns the expected HTTP status and body.
#   3. Exits with a non-zero code on any failure, failing the Jenkins stage.
#   4. Prints a clear diagnostic for every check.
#
# No destructive requests (no POST/PATCH/DELETE) are made.
# No credentials or sensitive information are logged.
# No port-forward background processes are started – we use the NodePort
# service that is already exposed by the cluster (nodePort: 30000).

set -euo pipefail

# ── Colour helpers ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

FAILURES=0

# ── Resolve application base URL ────────────────────────────────────────────
if [ -n "${1:-}" ]; then
    APP_URL="${1%/}"   # strip trailing slash if present
    info "Using supplied APP_URL: $APP_URL"
else
    # Minikube NodePort approach: get the Minikube IP and use nodePort 30000.
    MINIKUBE_IP=$(minikube ip 2>/dev/null || true)
    if [ -z "$MINIKUBE_IP" ]; then
        fail "Cannot determine Minikube IP. Pass APP_URL as first argument or ensure Minikube is running."
        exit 1
    fi
    APP_URL="http://${MINIKUBE_IP}:30000"
    info "Resolved Minikube NodePort URL: $APP_URL"
fi

# ── Wait for the application to become reachable ────────────────────────────
MAX_RETRIES=30
RETRY_INTERVAL=5
info "Waiting for application at $APP_URL/health (max $((MAX_RETRIES * RETRY_INTERVAL))s) ..."

for attempt in $(seq 1 $MAX_RETRIES); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 5 \
        --connect-timeout 3 \
        "${APP_URL}/health" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        info "Application reachable after ${attempt} attempt(s)."
        break
    fi

    if [ "$attempt" -eq "$MAX_RETRIES" ]; then
        fail "Application did not become reachable after $((MAX_RETRIES * RETRY_INTERVAL))s."
        fail "Last HTTP code from ${APP_URL}/health: ${HTTP_CODE}"
        exit 1
    fi

    info "Attempt $attempt/$MAX_RETRIES – got HTTP ${HTTP_CODE}, retrying in ${RETRY_INTERVAL}s ..."
    sleep "$RETRY_INTERVAL"
done

# ── Helper: assert HTTP status ───────────────────────────────────────────────
check_status() {
    local label="$1"
    local url="$2"
    local expected_status="$3"

    local actual_status
    actual_status=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        --connect-timeout 5 \
        "$url" 2>/dev/null || echo "000")

    if [ "$actual_status" = "$expected_status" ]; then
        pass "$label → HTTP $actual_status"
    else
        fail "$label → expected HTTP $expected_status, got HTTP $actual_status (URL: $url)"
        FAILURES=$((FAILURES + 1))
    fi
}

# ── Helper: assert response body contains substring ──────────────────────────
check_body_contains() {
    local label="$1"
    local url="$2"
    local expected_substring="$3"

    local body
    body=$(curl -s --max-time 10 --connect-timeout 5 "$url" 2>/dev/null || echo "")

    if echo "$body" | grep -qF "$expected_substring"; then
        pass "$label → body contains '$expected_substring'"
    else
        fail "$label → body did NOT contain '$expected_substring'"
        fail "  URL: $url"
        fail "  Actual body (first 200 chars): ${body:0:200}"
        FAILURES=$((FAILURES + 1))
    fi
}

# ── Smoke test checks ────────────────────────────────────────────────────────
info "─────────────────────────────────────────────────────"
info "Running smoke tests against: $APP_URL"
info "─────────────────────────────────────────────────────"

# 1. Health endpoint – must return 200 and {"status":"healthy"}
check_status      "Health endpoint HTTP status"          "${APP_URL}/health"     "200"
check_body_contains "Health endpoint body"               "${APP_URL}/health"     "healthy"

# 2. Status endpoint – must return 200 and report "running"
check_status      "Status endpoint HTTP status"          "${APP_URL}/api/status" "200"
check_body_contains "Status endpoint body – running"     "${APP_URL}/api/status" "running"
check_body_contains "Status endpoint body – project name" "${APP_URL}/api/status" "Student Task Manager"

# 3. Task list endpoint – must return 200 and a JSON array
check_status      "Task list endpoint HTTP status"       "${APP_URL}/api/tasks"  "200"
check_body_contains "Task list endpoint body is array"   "${APP_URL}/api/tasks"  "["

# 4. Metrics endpoint – must return 200 and expose the application counter
check_status      "Metrics endpoint HTTP status"         "${APP_URL}/metrics"    "200"
check_body_contains "Metrics endpoint exposes counter"   "${APP_URL}/metrics"    "demo_http_requests_total"

# 5. Home page – must return 200 and contain the app title
check_status      "Home page HTTP status"                "${APP_URL}/"           "200"
check_body_contains "Home page body"                     "${APP_URL}/"           "Student Task Manager"

# ── Result summary ───────────────────────────────────────────────────────────
info "─────────────────────────────────────────────────────"
if [ "$FAILURES" -eq 0 ]; then
    pass "All smoke tests passed."
    exit 0
else
    fail "$FAILURES smoke test(s) FAILED. Review the output above."
    exit 1
fi
