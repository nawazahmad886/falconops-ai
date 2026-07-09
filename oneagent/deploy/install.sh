#!/usr/bin/env bash
# FalconOpsAI OneAgent — Linux installer
# Usage:
#   curl -sL https://<falconops-host>/api/oneagent/install.sh | \
#     FALCONOPS_API_KEY=<key> FALCONOPS_BACKEND_URL=https://<falconops-host> bash
set -euo pipefail

BACKEND_URL="${FALCONOPS_BACKEND_URL:-}"
API_KEY="${FALCONOPS_API_KEY:-}"
INSTALL_DIR="/usr/local/bin"
CONF_DIR="/etc/falconops"
BUFFER_DIR="/var/lib/falconops/buffer"
SERVICE_FILE="/etc/systemd/system/falconops-oneagent.service"

say()  { echo -e "\033[1;36m[oneagent-install]\033[0m $*"; }
fail() { echo -e "\033[1;31m[oneagent-install] ERROR:\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root (sudo)"
[ -n "$BACKEND_URL" ] || fail "FALCONOPS_BACKEND_URL is required"
[ -n "$API_KEY" ]     || fail "FALCONOPS_API_KEY is required"
command -v systemctl >/dev/null || fail "systemd is required"

ARCH=$(uname -m)
case "$ARCH" in
  x86_64) BIN_ARCH="amd64" ;;
  aarch64|arm64) BIN_ARCH="arm64" ;;
  *) fail "unsupported architecture: $ARCH" ;;
esac

say "Downloading OneAgent binary (${BIN_ARCH})…"
mkdir -p "$CONF_DIR" "$BUFFER_DIR"
HTTP_CODE=$(curl -sL -w '%{http_code}' -o "$INSTALL_DIR/falconops-oneagent.tmp" \
  "$BACKEND_URL/api/oneagent/download/binary?arch=$BIN_ARCH")
if [ "$HTTP_CODE" != "200" ]; then
  say "Prebuilt binary not available (HTTP $HTTP_CODE) — building from source…"
  command -v go >/dev/null || fail "no prebuilt binary for $BIN_ARCH and Go toolchain not found. Install Go >= 1.22 and retry."
  TMP=$(mktemp -d)
  curl -sL -o "$TMP/src.tar.gz" "$BACKEND_URL/api/oneagent/download/source" || fail "source download failed"
  tar -xzf "$TMP/src.tar.gz" -C "$TMP"
  (cd "$TMP/oneagent" && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o "$INSTALL_DIR/falconops-oneagent.tmp" ./cmd/agent)
  rm -rf "$TMP"
fi
mv "$INSTALL_DIR/falconops-oneagent.tmp" "$INSTALL_DIR/falconops-oneagent"
chmod 0755 "$INSTALL_DIR/falconops-oneagent"

if [ ! -f "$CONF_DIR/agent.yaml" ]; then
  say "Writing $CONF_DIR/agent.yaml…"
  cat > "$CONF_DIR/agent.yaml" <<EOF
api_key: "$API_KEY"
backend_url: "$BACKEND_URL"
environment: "production"
enabled_plugins: [logs, metrics, traces]
sampling_rate: 1.0
log_filters:
  min_level: "info"
buffer_dir: $BUFFER_DIR
EOF
  chmod 0600 "$CONF_DIR/agent.yaml"
else
  say "$CONF_DIR/agent.yaml exists — keeping it"
fi

say "Installing systemd service…"
cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=FalconOpsAI OneAgent
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/falconops-oneagent --config /etc/falconops/agent.yaml
Restart=always
RestartSec=5
# Resource guardrails (matches <2% CPU / <100MB targets)
CPUQuota=20%
MemoryMax=128M
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=/var/lib/falconops

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now falconops-oneagent

sleep 2
if systemctl is-active --quiet falconops-oneagent; then
  say "✔ OneAgent is running.  Health: curl -s http://127.0.0.1:8126/health"
  say "  Logs:   journalctl -u falconops-oneagent -f"
else
  fail "service failed to start — check: journalctl -u falconops-oneagent -n 50"
fi
