#!/usr/bin/env bash
# FalconOps AI — Enable real HTTPS via Let's Encrypt (certbot, webroot method)
#
# Prerequisites:
#   - The stack is already running (docker compose up -d) with nginx serving
#     plain HTTP on port 80.
#   - DOMAIN's DNS A/AAAA record already points at this host, and port 80 is
#     reachable from the public internet (Let's Encrypt validates over HTTP).
#
# What this does:
#   1. Requests a real certificate for DOMAIN via the certbot service (webroot
#      method — validated through nginx's /.well-known/acme-challenge/ location).
#   2. On success, renders nginx/https.conf.template -> nginx/default.conf with
#      your domain substituted (backs up the previous config first).
#   3. Reloads nginx. The certbot service (already running in the background)
#      handles renewal automatically every 12h check / ~60-90 days.
#
# Usage:
#   ./setup-https.sh --domain your-domain.com [--email you@example.com]
set -euo pipefail

say()  { echo -e "\033[1;36m[setup-https]\033[0m $*"; }
fail() { echo -e "\033[1;31m[setup-https] ERROR:\033[0m $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
[ -f docker-compose.yml ] || fail "docker-compose.yml not found — run this from the repo root"

DOMAIN=""
EMAIL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[ -n "$DOMAIN" ] || fail "usage: ./setup-https.sh --domain your-domain.com [--email you@example.com]"
if [[ "$DOMAIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  fail "Let's Encrypt cannot issue certs for a bare IP address — you need a real DNS domain pointed at this host."
fi

docker compose ps nginx --format '{{.State}}' 2>/dev/null | grep -q running || \
  fail "nginx isn't running — start the stack first: docker compose up -d"

say "Requesting a certificate for $DOMAIN via Let's Encrypt (webroot method)..."
EMAIL_ARGS=(--email "$EMAIL" --no-eff-email)
[ -n "$EMAIL" ] || EMAIL_ARGS=(--register-unsafely-without-email)

if ! docker compose run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    -d "$DOMAIN" \
    "${EMAIL_ARGS[@]}" \
    --agree-tos --non-interactive; then
  fail "Certificate request failed — check that $DOMAIN's DNS points at this host and port 80 is reachable from the internet. Nothing was changed (still on HTTP)."
fi

say "Certificate issued. Switching nginx to HTTPS..."
cp nginx/default.conf "nginx/default.conf.bak.$(date +%s)"
sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx/https.conf.template > nginx/default.conf

docker compose exec nginx nginx -s reload || docker compose restart nginx

say "Done. FalconOps AI is now served over https://$DOMAIN"
say "Renewal is automatic (the certbot service checks every 12h) — no further action needed."
