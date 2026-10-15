#!/usr/bin/env bash
#
# AgentFault — bring up the whole local testbed and print the ports.
#
# What it starts (idempotently):
#   1. a single-node kind cluster
#   2. the dashboard + worker images, loaded into the cluster
#   3. metrics-server (for the CPU-based HPA)
#   4. kube-prometheus-stack (Prometheus, Grafana, Alertmanager)
#   5. the AgentFault Helm chart (dashboard + autoscaled worker + dashboards)
#   6. the AgentFault PrometheusRule
#   7. port-forwards for Grafana, Prometheus, the dashboard API and the worker
#   8. the React frontend (vite preview)
#
# Re-running is safe: anything already up is detected and left alone.
#
# Usage:
#   ./start-cluster.sh            # start everything, report ports
#   ./start-cluster.sh --stop     # stop the port-forwards + frontend
#   ./start-cluster.sh --delete   # also delete the kind cluster
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CLUSTER_NAME="${CLUSTER_NAME:-agentfault}"
KIND_NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.31.0}"
NAMESPACE="${NAMESPACE:-agentfault}"
MONITORING_NS="${MONITORING_NS:-monitoring}"
RUN_DIR="${AGENTFAULT_RUN_DIR:-/tmp/agentfault-run}"
HELM_BIN="${HELM_BIN:-helm}"

DASHBOARD_IMG="${DASHBOARD_IMG:-agentfault/dashboard:dev}"
WORKER_IMG="${WORKER_IMG:-agentfault/worker:dev}"

GRAFANA_PORT="${GRAFANA_PORT:-3000}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8000}"
WORKER_PORT="${WORKER_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"

c_blue=$'\033[1;34m'; c_green=$'\033[1;32m'; c_yellow=$'\033[1;33m'; c_off=$'\033[0m'
log()  { printf '%s==>%s %s\n' "$c_blue" "$c_off" "$*"; }
ok()   { printf '%s  =%s %s\n' "$c_green" "$c_off" "$*"; }
warn() { printf '%s[!]%s %s\n' "$c_yellow" "$c_off" "$*" >&2; }
die()  { printf '%s[x]%s %s\n' "$c_yellow" "$c_off" "$*" >&2; exit 1; }

require() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# --- stop / teardown ------------------------------------------------------
stop_forwards() {
  if [ -d "$RUN_DIR" ]; then
    for f in "$RUN_DIR"/*.pid; do
      [ -e "$f" ] || continue
      pid="$(cat "$f" 2>/dev/null || true)"
      if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        ok "stopped $(basename "$f" .pid) (pid $pid)"
      fi
      rm -f "$f"
    done
  fi
}

if [ "${1:-}" = "--stop" ] || [ "${1:-}" = "--delete" ]; then
  log "Stopping port-forwards and frontend"
  stop_forwards
  if [ "${1:-}" = "--delete" ]; then
    require kind
    log "Deleting kind cluster '$CLUSTER_NAME'"
    kind delete cluster --name "$CLUSTER_NAME" || true
  fi
  ok "done"
  exit 0
fi

# --- prerequisites --------------------------------------------------------
require kind
require kubectl
require "$HELM_BIN"
require docker
require npm
mkdir -p "$RUN_DIR"

# --- 1. cluster -----------------------------------------------------------
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  ok "kind cluster '$CLUSTER_NAME' already exists"
else
  log "Creating kind cluster '$CLUSTER_NAME'"
  kind create cluster --name "$CLUSTER_NAME" --image "$KIND_NODE_IMAGE"
fi

# --- 2. images ------------------------------------------------------------
for img in "$DASHBOARD_IMG" "$WORKER_IMG"; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    ok "image present: $img"
  else
    die "image $img not built — run: docker build -f Dockerfile.${img##*/} -t $img ."
  fi
done
log "Loading images into kind"
kind load docker-image --name "$CLUSTER_NAME" "$DASHBOARD_IMG" "$WORKER_IMG"

# --- 3. metrics-server ----------------------------------------------------
if kubectl get deploy metrics-server -n kube-system >/dev/null 2>&1; then
  ok "metrics-server already installed"
else
  log "Installing metrics-server"
  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
  kubectl patch -n kube-system deployment metrics-server --type=json \
    -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
fi

# --- 4. monitoring stack --------------------------------------------------
if "$HELM_BIN" status kube-prometheus-stack -n "$MONITORING_NS" >/dev/null 2>&1; then
  ok "kube-prometheus-stack already installed"
else
  log "Installing kube-prometheus-stack"
  "$HELM_BIN" repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
  "$HELM_BIN" repo update >/dev/null 2>&1 || true
  "$HELM_BIN" install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
    -n "$MONITORING_NS" --create-namespace \
    -f "$ROOT/deploy/monitoring/values-kube-prometheus-stack.yaml"
fi

# --- 5. agentfault chart --------------------------------------------------
if "$HELM_BIN" status agentfault -n "$NAMESPACE" >/dev/null 2>&1; then
  log "Upgrading AgentFault release"
  "$HELM_BIN" upgrade agentfault "$ROOT/deploy/helm/agentfault" -n "$NAMESPACE"
else
  log "Installing AgentFault release"
  "$HELM_BIN" install agentfault "$ROOT/deploy/helm/agentfault" -n "$NAMESPACE" --create-namespace
fi

# --- 6. alert rules -------------------------------------------------------
log "Applying PrometheusRule"
kubectl apply -f "$ROOT/deploy/monitoring/prometheus/agentfault-prometheusrule.yaml" -n "$MONITORING_NS"

# --- 7. wait for workloads ------------------------------------------------
log "Waiting for rollouts"
kubectl rollout status deploy/agentfault-agentfault-dashboard -n "$NAMESPACE" --timeout=180s || warn "dashboard rollout not ready"
kubectl rollout status deploy/agentfault-agentfault-worker    -n "$NAMESPACE" --timeout=180s || warn "worker rollout not ready"
kubectl rollout status deploy/kube-prometheus-stack-grafana   -n "$MONITORING_NS" --timeout=180s || warn "grafana rollout not ready"

# --- 8. port-forwards -----------------------------------------------------
# pf <name> <namespace> <service> <local> <remote>
pf() {
  local name="$1" ns="$2" svc="$3" lp="$4" rp="$5"
  local pidfile="$RUN_DIR/$name.pid" logfile="$RUN_DIR/$name.log"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    ok "$name already forwarding (pid $(cat "$pidfile"))"
    return
  fi
  if port_open "$lp"; then
    warn "port $lp already in use — leaving it as-is ($name)"
    return
  fi
  nohup kubectl port-forward -n "$ns" "svc/$svc" "$lp:$rp" >"$logfile" 2>&1 &
  echo $! > "$pidfile"
  ok "$name forwarding on localhost:$lp (pid $(cat "$pidfile"))"
}

log "Starting port-forwards"
pf grafana    "$MONITORING_NS" kube-prometheus-stack-grafana    "$GRAFANA_PORT"    80
pf prometheus "$MONITORING_NS" kube-prometheus-stack-prometheus "$PROMETHEUS_PORT" 9090
pf dashboard  "$NAMESPACE"     agentfault-agentfault-dashboard  "$DASHBOARD_PORT"  8000
pf worker     "$NAMESPACE"     agentfault-agentfault-worker     "$WORKER_PORT"     8080

# --- 9. frontend ----------------------------------------------------------
if port_open "$FRONTEND_PORT"; then
  ok "frontend already serving on localhost:$FRONTEND_PORT"
else
  log "Building and starting the frontend"
  ( cd "$ROOT/frontend" && npm run build >/dev/null 2>&1 )
  nohup env npm --prefix "$ROOT/frontend" run preview -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
    >"$RUN_DIR/frontend.log" 2>&1 &
  echo $! > "$RUN_DIR/frontend.pid"
  ok "frontend starting on localhost:$FRONTEND_PORT (pid $(cat "$RUN_DIR/frontend.pid"))"
fi

# --- 10. report -----------------------------------------------------------
sleep 2
printf '\n%s=== AgentFault environment is up ===%s\n' "$c_green" "$c_off"
printf '  %-12s %-30s %s\n' "Grafana"    "http://localhost:$GRAFANA_PORT"                 "($GRAFANA_USER/$GRAFANA_PASSWORD; dashboards: agentfault folder)"
printf '  %-12s %-30s %s\n' "Prometheus" "http://localhost:$PROMETHEUS_PORT"              "(targets, rules, /-/reload)"
printf '  %-12s %-30s %s\n' "Dashboard"  "http://localhost:$DASHBOARD_PORT/api/meta"      "(dataset API)"
printf '  %-12s %-30s %s\n' "Worker"     "http://localhost:$WORKER_PORT/metrics"          "(Prometheus metrics)"
printf '  %-12s %-30s %s\n' "Frontend"   "http://localhost:$FRONTEND_PORT"                "(React console)"
printf '\n  pods:   kubectl get pods -A\n'
printf '  hpa:    kubectl get hpa -n %s -w\n' "$NAMESPACE"
printf '  stop:   %s --stop     (add --delete to remove the cluster)\n\n' "$0"
