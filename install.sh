#!/usr/bin/env bash
# FalconOps AI — generic Debian/Ubuntu installer (Docker Compose route)
#
# For any Docker-capable VPS/cloud host running Debian or Ubuntu (the default
# on most providers — DigitalOcean, Linode, Hetzner, a bare EC2/VM, etc.). For
# RHEL/CentOS/Rocky/Alma, use install-rhel.sh instead.
#
# What this does:
#   1. Installs Docker CE + the compose plugin (apt, official Docker repo)
#   2. Opens only 80/443 via ufw (nginx is the sole external entrypoint —
#      mongo/redis/backend/frontend are bound to 127.0.0.1 in docker-compose.yml)
#   3. Generates the repo-root .env (random Mongo/Redis passwords) and
#      backend/.env (random JWT secret, CORS for your domain), if they don't
#      already exist (safe to re-run — never overwrites)
#   4. Builds and starts the stack
#
# Usage (run as root, from the repo root):
#   ./install.sh --domain your-domain-or-ip [--llm-provider ollama|openai|anthropic|gemini|rule_based]
#
# Optional flags:
#   --skip-docker      skip Docker install (use if already installed)
#   --skip-firewall    skip ufw changes (use if you manage it separately)
#
# Once DNS for a real domain points at this host, enable real HTTPS with:
#   ./setup-https.sh --domain your-domain.com
set -euo pipefail

say()  { echo -e "\033[1;36m[falconops-install]\033[0m $*"; }
fail() { echo -e "\033[1;31m[falconops-install] ERROR:\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root (sudo ./install.sh ...)"

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
[ -f /etc/os-release ] || fail "/etc/os-release not found — this script targets Debian/Ubuntu"
. /etc/os-release
say "Detected: ${PRETTY_NAME:-$ID $VERSION_ID}"
case "$ID" in
  debian|ubuntu) ;;
  *) say "WARNING: untested distro '$ID' — proceeding anyway (this script assumes apt + ufw + systemd)" ;;
esac

# ─────────────────────────────────────────────
#  2. Docker install
# ─────────────────────────────────────────────
if [ "$SKIP_DOCKER" -eq 1 ]; then
  say "Skipping Docker install (--skip-docker)"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  say "Docker + compose plugin already present, skipping install."
else
  say "Installing Docker CE + compose plugin via apt..."
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$ID $VERSION_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
  say "Docker installed: $(docker --version)"
fi

# ─────────────────────────────────────────────
#  3. Firewall — expose only 80/443 (nginx). Everything else is bound to
#     127.0.0.1 in docker-compose.yml and never needs a firewall hole.
# ─────────────────────────────────────────────
if [ "$SKIP_FIREWALL" -eq 1 ]; then
  say "Skipping firewall changes (--skip-firewall)"
elif command -v ufw >/dev/null 2>&1; then
  ufw allow 80/tcp
  ufw allow 443/tcp
  if ufw status | grep -q "Status: active"; then
    say "ufw: opened 80/443 on an already-active firewall."
  else
    say "ufw: rules added but firewall is inactive — 'ufw enable' if you want it enforced."
  fi
else
  say "Installing ufw..."
  apt-get install -y ufw
  ufw allow OpenSSH || true
  ufw allow 80/tcp
  ufw allow 443/tcp
  say "WARNING: ufw was just installed but NOT enabled (to avoid locking you out over SSH) — review 'ufw status' and run 'ufw enable' yourself once you've confirmed SSH access is allowed."
fi

# ─────────────────────────────────────────────
#  4a. repo-root .env — MONGO_ROOT_PASSWORD / REDIS_PASSWORD used by
#      docker-compose.yml's variable substitution.
# ─────────────────────────────────────────────
if [ -f .env ]; then
  say "repo-root .env already exists — leaving it untouched."
else
  say "Generating repo-root .env (random Mongo/Redis passwords)..."
  cat > .env <<EOF
# Generated by install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Used by docker-compose.yml's variable substitution for the mongo/redis
# containers — do NOT confuse with backend/.env (the application's own config).
MONGO_ROOT_PASSWORD=$(openssl rand -hex 24)
REDIS_PASSWORD=$(openssl rand -hex 24)
EOF
  chmod 600 .env
  say "Wrote repo-root .env (mode 600)."
fi

# ─────────────────────────────────────────────
#  4b. backend/.env — generate once, never overwrite an existing file
# ─────────────────────────────────────────────
if [ -f backend/.env ]; then
  say "backend/.env already exists — leaving it untouched."
else
  say "Generating backend/.env (random JWT secret, CORS for $DOMAIN, LLM provider=$LLM_PROVIDER)..."
  JWT_SECRET="$(openssl rand -hex 32)"
  LICENSE_SECRET="$(openssl rand -hex 32)"
  cat > backend/.env <<EOF
# Generated by install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
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
say "For real HTTPS once DNS points here: ./setup-https.sh --domain your-domain.com"
