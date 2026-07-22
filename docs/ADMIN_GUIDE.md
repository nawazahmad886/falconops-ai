# FalconOps AI — Admin Guide

Operational guide for whoever runs FalconOps AI day-to-day: installing it, starting/
stopping it, configuring it, and the checks to run when something looks wrong. For what
each part of the system actually does, see [`COMPONENTS.md`](./COMPONENTS.md).

Everything below reflects the actual scripts/compose file in this repo
(`install.sh`, `install-rhel.sh`, `setup-https.sh`, `docker-compose.yml`) — not a
generic Docker tutorial.

---

## 1. First-time install

Two installers, pick the one matching your OS (both do the same thing: install Docker,
open only ports 80/443 in the firewall, generate credentials, build, and start):

```bash
# Debian/Ubuntu (DigitalOcean, Linode, Hetzner, a bare VM, etc.)
sudo ./install.sh --domain your-domain-or-ip

# RHEL/CentOS/Rocky/Alma 7 or 8
sudo ./install-rhel.sh --domain your-domain-or-ip
```

Optional flags on both: `--llm-provider ollama|openai|anthropic|gemini|rule_based`
(default `rule_based` — works with no API key, but only handles simple templated
requests), `--skip-docker`, `--skip-firewall`.

What this generates automatically (never overwrites an existing file, safe to re-run):
- Repo-root `.env` — `MONGO_ROOT_PASSWORD` / `REDIS_PASSWORD` (random, mode 600).
- `backend/.env` — `JWT_SECRET_KEY` (random), `CORS_ORIGINS` for your domain,
  `LICENSE_SECRET`, LLM provider config.

At the end you'll see `Done. Open http://your-domain-or-ip in a browser.` Nginx is the
only externally-reachable service — mongo/redis/backend/frontend are all bound to
`127.0.0.1` only.

**Enable real HTTPS** once DNS actually points at the host (needs a real domain, not a
bare IP):
```bash
./setup-https.sh --domain your-domain.com
```
This issues a Let's Encrypt cert via certbot (webroot method) and reloads nginx with the
HTTPS config. Auto-renewal runs via the `certbot` container already in
`docker-compose.yml` (checks every 12h).

---

## 2. Start / stop / restart

All commands run from the repo root, once `backend/.env` exists (the installers create
it; for a manual setup, copy `.env.example` → `.env` and fill in the two passwords
first).

| Action | Command |
|---|---|
| Start everything (detached) | `docker compose up -d` |
| Stop everything (keeps data) | `docker compose stop` |
| Stop and remove containers (keeps volumes/data) | `docker compose down` |
| Restart one service | `docker compose restart backend` (or `frontend`, `nginx`, `mongo`, `redis`) |
| Rebuild after a backend code change | `docker compose build backend && docker compose up -d` |
| Rebuild after a frontend code/env change | `docker compose build frontend && docker compose up -d` — required after changing `REACT_APP_BACKEND_URL`, since it's baked into the JS at build time, not read at runtime |
| Full stack rebuild | `docker compose build && docker compose up -d` |
| **Destructive**: wipe all data (mongo/redis/metrics volumes) | `docker compose down -v` — only do this deliberately, it deletes the database |

Check status: `docker compose ps`. Tail logs: `docker compose logs -f` (all services) or
`docker compose logs -f backend` (one service).

---

## 3. Health checks

- `GET http://localhost/api/health` (or `https://your-domain/api/health` once HTTPS is
  set up) — returns `{"status": "healthy", "service": "FalconOps AI", "storage": {...}}`.
  The backend container's own Docker healthcheck polls this every 30s.
- `docker compose ps` — all services should show `Up` / `(healthy)`. `mongo` and
  `backend` have real healthchecks configured; if `mongo` never reports healthy,
  `backend` will never start (it waits on `condition: service_healthy`).
- Backend logs a full **env preflight** on every startup (`docker compose logs backend
  | head -50`) — flags a missing `MONGO_URL`/`DB_NAME`, a default/insecure
  `JWT_SECRET_KEY`, or no LLM provider configured, before anything else goes wrong
  because of it.

---

## 4. Configuration reference

Two separate `.env` files, don't confuse them:

**Repo-root `.env`** (docker-compose variable substitution only):
```
MONGO_ROOT_PASSWORD=<random hex>
REDIS_PASSWORD=<random hex>
```

**`backend/.env`** (the application's own config — this is the one you edit to turn on
real AI features):
```
JWT_SECRET_KEY=<random hex, auto-generated>
CORS_ORIGINS=http://your-domain,https://your-domain
ENVIRONMENT=production

# LLM provider — rule_based (default, no key needed) | ollama | openai | anthropic | gemini
LLM_PROVIDER=rule_based
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GOOGLE_API_KEY=
# OLLAMA_BASE_URL=http://localhost:11434

# Optional integrations
# STRIPE_API_KEY=
# STRIPE_WEBHOOK_SECRET=
# RESEND_API_KEY=       — needed for scheduled/weekly email reports
# SENDER_EMAIL=
# TWILIO_ACCOUNT_SID=   — SMS notifications, if used
# TWILIO_AUTH_TOKEN=
```
After editing `backend/.env`, apply changes with `docker compose up -d` (no rebuild
needed — it's read at container start, not baked in).

`MONGO_URL`, `DB_NAME`, `REDIS_URL`, `VICTORIA_METRICS_URL`, `KAFKA_BOOTSTRAP_SERVERS`
are deliberately **not** set in `backend/.env` for the Docker route — `docker-compose.yml`
injects them pointing at the sidecar containers. Only set these yourself if running the
backend outside Docker.

---

## 5. Common admin operations

**Create a new tenant / admin user** — via the app's signup flow (`/api/auth/register`)
for the first account, then use the Admin Console (`/admin`) or `tenants.py` routes to
manage additional tenants. Elevated roles (anything above `user`/`viewer`) can only be
assigned by an existing global admin — this is enforced server-side, not just hidden in
the UI.

**Rotate the JWT secret** — edit `JWT_SECRET_KEY` in `backend/.env`, then
`docker compose up -d`. This invalidates all existing sessions (users must log in
again) — there's no separate refresh-token mechanism to preserve.

**Back up MongoDB**:
```bash
docker compose exec mongo mongodump --username root --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin --archive=/tmp/backup.archive
docker compose cp mongo:/tmp/backup.archive ./falconops-backup-$(date +%F).archive
```

**Restore MongoDB**:
```bash
docker compose cp ./falconops-backup-YYYY-MM-DD.archive mongo:/tmp/backup.archive
docker compose exec mongo mongorestore --username root --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin --archive=/tmp/backup.archive --drop
```

**Enable a real LLM provider** (beyond the default rule-based fallback) — set
`LLM_PROVIDER` and the matching API key in `backend/.env`, `docker compose up -d`. Verify
via any AI feature (e.g. `AIAgentsPage.js`'s Config tab shows the active mode/provider).

**Wire in real distributed tracing** — point an OpenTelemetry exporter at
`https://your-domain/api/otel/v1/traces` (`OTEL_EXPORTER_OTLP_PROTOCOL=http/json` is
required — protobuf/gRPC is not supported). See `APMQuickstartPage.js` in-app for
copy-paste exporter config. Once traces arrive, the Service Map and Service Detail pages
populate automatically — no further config needed.

**Check what's actually populated vs. empty** — the legacy APM pipeline (`/api/apm/*`)
requires an external agent to POST to `/api/apm/ingest/*`; nothing in this codebase does
that automatically. If that dashboard looks empty, that's expected unless you've wired
one up — use the OTLP-based APM Traces / Service Map pages instead, which are fed by
real ingestion.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `backend` container restarts in a loop | Check `docker compose logs backend` for the env preflight output first — almost always a missing/malformed `backend/.env` value |
| `mongo` never becomes healthy | Check `MONGO_ROOT_PASSWORD` is set in the repo-root `.env` and matches what the container was first initialized with (changing the password after the volume already has data won't retroactively change the DB's own auth) |
| Frontend loads but API calls fail (CORS errors in browser console) | `CORS_ORIGINS` in `backend/.env` doesn't include the origin you're browsing from — add it and `docker compose up -d` |
| Changed `REACT_APP_BACKEND_URL` but frontend still calls the old URL | You need to **rebuild** the frontend image (`docker compose build frontend && docker compose up -d`) — this value is baked into the JS bundle at build time |
| AI features all return generic/templated answers | No LLM provider configured — `LLM_PROVIDER` defaults to `rule_based`; set a real provider + key in `backend/.env` |
| Service Map / APM pages show no data | No OTLP traces have been ingested yet — confirm an exporter is actually configured to POST to `/api/otel/v1/traces`, and that its protocol is `http/json` not gRPC |
| Certbot / HTTPS setup fails | `setup-https.sh` requires a real domain with DNS already pointing at this host on port 80 — it explicitly refuses a bare IP address |
