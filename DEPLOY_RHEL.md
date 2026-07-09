# FalconOps AI — RHEL/CentOS/Rocky/Alma 7 & 8 Deployment (Docker Compose)

Docker Compose is the only realistic path on RHEL-family 7 hosts, and the recommended path on 8:
this stack pins **MongoDB 8** (MongoDB dropped RHEL 7 support upstream entirely), **Node 22** for
the frontend build (needs glibc ≥ 2.28; RHEL 7 ships 2.17), and a heavy Python ML dependency chain
(`torch`, `transformers`, `chromadb`, `onnxruntime` — used by the RAG layer in
`backend/requirements.txt`) that's fragile to build from source on an old base image. Docker
containers carry their own userspace, so none of that depends on the host OS version.

Base images are picked for runway, not just "latest": Python 3.12 (backend, EOL Oct 2028), Node 22
(frontend build only — Maintenance LTS, EOL Apr 2027), MongoDB 8 (EOL ~2029). We moved off Python
3.11 and Node 20 specifically because Node 20 is already past its April 2026 EOL and Python 3.11
reaches EOL October 2026 — both were live risks, not just staleness.

## ⚡ TL;DR

```bash
sudo ./install-rhel.sh --domain your-domain-or-ip
# then open http://your-domain-or-ip
```

That script installs Docker, opens only 80/443 in firewalld, generates `backend/.env` with a
random JWT secret, and runs `docker compose build && up -d`. See `--help`-style usage at the top
of `install-rhel.sh` for `--llm-provider`, `--skip-docker`, `--skip-firewall`.

## 1. Prerequisites / package list

| Component | RHEL/CentOS **7** (`yum`) | RHEL/CentOS/Rocky/Alma **8** (`dnf`) |
|---|---|---|
| Repo tooling | `yum-utils` | `dnf-plugins-core` |
| Device mapper (Docker storage driver on el7) | `device-mapper-persistent-data`, `lvm2` | — (overlay2 default on el8) |
| Docker | `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-compose-plugin` from `download.docker.com/linux/centos/docker-ce.repo` | same packages, same repo |
| SELinux helpers | `policycoreutils-python-utils` | `policycoreutils-python-utils` |
| Misc | `git`, `curl` | `git`, `curl` |

Everything else (Python 3.12, Node 22, MongoDB 8, Redis 7, nginx) lives **inside** the containers
built from `backend/Dockerfile` / `frontend/Dockerfile` / the `mongo:8`, `redis:7-alpine`,
`nginx:alpine` images in `docker-compose.yml` — nothing else needs to be installed on the host.

`install-rhel.sh` installs the table above for you; it's listed here for anyone who wants to
provision the host through their own config-management tooling instead.

## 2. Resource sizing

torch + transformers + chromadb + Mongo + Redis running together want, at minimum:

- **4 vCPU / 8 GB RAM / 20+ GB disk** (first `docker compose build` pulls multi-GB ML wheels)
- Outbound internet access during build (PyPI, npm registry, Docker Hub) unless you're mirroring

## 3. Network exposure

`docker-compose.yml` publishes `mongo` (27017), `redis` (6379), `backend` (8001) and `frontend`
(3000) to `127.0.0.1` only — nginx (`80`/`443`) is the sole service reachable from the network.
Neither Mongo nor Redis has auth configured in this compose file, so **do not** change those
bindings to `0.0.0.0` without adding auth first.

## 4. TLS

`nginx/default.conf` ships an HTTPS server block commented out. Get a cert (e.g.
`certbot --nginx`, needs `epel-release` + `certbot` + `python3-certbot-nginx` on either version),
drop `fullchain.pem`/`privkey.pem` into `nginx/ssl/`, uncomment the block, and
`docker compose restart nginx`.

## 5. Manual steps (if you'd rather not run the script)

```bash
# el7
yum install -y yum-utils device-mapper-persistent-data lvm2 git curl policycoreutils-python-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# el8
dnf install -y dnf-plugins-core git curl policycoreutils-python-utils
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# both — open the gateway ports, then build/run
firewall-cmd --permanent --add-service=http --add-service=https && firewall-cmd --reload
# write backend/.env yourself (see install-rhel.sh's heredoc for the required keys:
# JWT_SECRET_KEY, CORS_ORIGINS, LLM_PROVIDER, and optional Stripe/Resend/Twilio keys)
docker compose build
docker compose up -d
curl -f http://127.0.0.1:8001/api/health
```

## 6. Updating

```bash
git pull
docker compose build
docker compose up -d
```

`backend/.env` is never touched by the installer on re-run, so secrets survive updates.
