#!/usr/bin/env bash
# FalconOps AI — RHEL/CentOS/Rocky/Alma 7 & 8 installer (Docker Compose route)
#
# Why Docker and not a native install: this stack pins MongoDB 7 (dropped RHEL 7
# support upstream), Node 20 (needs glibc >= 2.28; RHEL 7 ships 2.17), and a
# heavy Python ML dependency chain (torch/transformers/chromadb/onnxruntime for
# the RAG layer) that's fragile to build from source on an old base image.
# Docker sidesteps all of that — the host OS version stops mattering once
# everything runs in containers.
#
# What this script does:
#   1. Installs Docker CE + the compose plugin (yum on el7, dnf on el8+)
#   2. Opens only 80/443 in firewalld (nginx is the sole external entrypoint —
#      mongo/redis/backend/frontend are bound to 127.0.0.1 in docker-compose.yml)
#   3. Generates backend/.env with a random JWT secret + your domain's CORS
#      origin, if one doesn't already exist (safe to re-run — never overwrites)
#   4. Builds and starts the stack
#
# Usage (run as root, from the repo root):
#   ./install-rhel.sh --domain your-domain-or-ip [--llm-provider ollama|openai|anthropic|gemini|rule_based]
#
# Optional flags:
#   --skip-docker      skip Docker install (use if already installed)
#   --skip-firewall    skip firewalld changes (use if you manage it separately)
set -euo pipefail

say()  { echo -e "\033[1;36m[falconops-install]\033[0m $*"; }
fail() { echo -e "\033[1;31m[falconops-install] ERROR:\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root (sudo ./install-rhel.sh ...)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
[ -f docker-compose.yml ] || fail "docker-compose.yml not found — run this from the repo root"

DOMAIN=""
LLM_PROVIDER="rule_based"
SKIP_DOCKER=0
SKIP_FIREWALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --llm-provider) LLM_PROVIDER="$2"; shift 2 ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --skip-firewall) SKIP_FIREWALL=1; shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done

if [ -z "$DOMAIN" ]; then
  DOMAIN=$(hostname -I 2>/dev/null | awk '{print $1}')
  [ -n "$DOMAIN" ] || fail "--domain not given and couldn't auto-detect an IP — pass --domain your-domain-or-ip"
  say "No --domain given, using detected IP: $DOMAIN"
fi

# ─────────────────────────────────────────────
#  1. OS detection
# ─────────────────────────────────────────────
[ -f /etc/os-release ] || fail "/etc/os-release not found — this script targets RHEL/CentOS/Rocky/Alma"
. /etc/os-release
MAJOR_VER="${VERSION_ID%%.*}"
say "Detected: ${PRETTY_NAME:-$ID $VERSION_ID} (major version $MAJOR_VER)"

case "$ID" in
  rhel|centos|rocky|almalinux) ;;
  *) say "WARNING: untested distro '$ID' — proceeding anyway (this script assumes yum/dnf + firewalld + systemd)" ;;
esac

if [ "$MAJOR_VER" -lt 7 ]; then
  fail "RHEL/CentOS < 7 is not supported."
fi
if [ "$MAJOR_VER" -eq 7 ]; then
  PKG=yum
  say "el7 detected — Docker route is REQUIRED here (MongoDB 7 / Node 20 do not support el7 natively)."
else
  PKG=dnf
fi

# ─────────────────────────────────────────────
#  2. Docker install
# ─────────────────────────────────────────────
if [ "$SKIP_DOCKER" -eq 1 ]; then
  say "Skipping Docker install (--skip-docker)"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  say "Docker + compose plugin already present, skipping install."
else
  say "Installing Docker CE + compose plugin via $PKG..."
  if [ "$PKG" = "yum" ]; then
    yum install -y yum-utils device-mapper-persistent-data lvm2 git curl policycoreutils-python-utils
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  else
    dnf install -y dnf-plugins-core git curl policycoreutils-python-utils
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
  systemctl enable --now docker
  say "Docker installed: $(docker --version)"
fi

# ─────────────────────────────────────────────
#  3. Firewall — expose only 80/443 (nginx). Everything else is bound to
#     127.0.0.1 in docker-compose.yml and never needs a firewall hole.
# ─────────────────────────────────────────────
if [ "$SKIP_FIREWALL" -eq 1 ]; then
  say "Skipping firewall changes (--skip-firewall)"
elif command -v firewall-cmd >/dev/null 2>&1; then
  systemctl enable --now firewalld 2>/dev/null || true
  if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
    say "firewalld: opened http/https, reloaded."
  else
    say "WARNING: firewalld installed but not active — leaving as-is. Ensure 80/443 are reachable another way."
  fi
else
  say "WARNING: firewalld not found — skipping firewall config. Ensure 80/443 are reachable and nothing else is."
fi

# ─────────────────────────────────────────────
#  4. backend/.env — generate once, never overwrite an existing file
# ─────────────────────────────────────────────
if [ -f backend/.env ]; then
  say "backend/.env already exists — leaving it untouched."
else
  say "Generating backend/.env (random JWT secret, CORS for $DOMAIN, LLM provider=$LLM_PROVIDER)..."
  JWT_SECRET="$(openssl rand -hex 32)"
  LICENSE_SECRET="$(openssl rand -hex 32)"
  cat > backend/.env <<EOF
# Generated by install-rhel.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# MONGO_URL / DB_NAME / REDIS_URL / VICTORIA_METRICS_URL / KAFKA_BOOTSTRAP_SERVERS
# are overridden by docker-compose.yml's 'environment:' block to point at the
# sidecar containers — no need to set them here for the Docker route.

JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
LICENSE_SECRET=$LICENSE_SECRET

CORS_ORIGINS=http://$DOMAIN,https://$DOMAIN
ENVIRONMENT=production
PUBLIC_BASE_URL=http://$DOMAIN
APP_URL=http://$DOMAIN

# LLM provider: ollama | openai | anthropic | gemini | emergent | rule_based
# rule_based (default) needs no key but only handles simple templated requests —
# set a real provider + key below for full AI Copilot / RCA / Log Analyzer.
LLM_PROVIDER=$LLM_PROVIDER
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GOOGLE_API_KEY=
# OLLAMA_BASE_URL=http://localhost:11434

# Optional integrations — uncomment and fill in as needed
# STRIPE_API_KEY=
# STRIPE_WEBHOOK_SECRET=
# RESEND_API_KEY=
# SENDER_EMAIL=
# TWILIO_ACCOUNT_SID=
# TWILIO_AUTH_TOKEN=
# TWILIO_WHATSAPP_FROM=
EOF
  chmod 600 backend/.env
  say "Wrote backend/.env (mode 600). Edit it to add LLM/Stripe/Resend keys, then re-run 'docker compose up -d' to pick up changes."
fi

# ─────────────────────────────────────────────
#  5. Build + start
# ─────────────────────────────────────────────
say "Building images (this pulls torch/transformers/chromadb — can take a while on first run)..."
REACT_APP_BACKEND_URL="http://$DOMAIN" docker compose build

say "Starting the stack..."
docker compose up -d

say "Waiting for backend health check..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8001/api/health" >/dev/null 2>&1; then
    say "Backend healthy."
    break
  fi
  sleep 2
  [ "$i" -eq 30 ] && say "WARNING: backend not healthy after 60s — check 'docker compose logs backend'"
done

say "Done. Open http://$DOMAIN in a browser."
say "Logs:   docker compose logs -f"
say "Status: docker compose ps"
