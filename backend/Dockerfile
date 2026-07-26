# ===================== Stage 1: Builder =====================
FROM python:3.12-slim AS builder

WORKDIR /build

# Build deps (needed for some C-extensions like cryptography, pillow, reportlab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===================== Stage 2: Runtime =====================
FROM python:3.12-slim

WORKDIR /app

# Runtime deps only — no build toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libffi8 libssl3 libjpeg62-turbo zlib1g libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r falcon && useradd -r -g falcon -u 1001 -d /app falcon \
    && mkdir -p /tmp/falconops_reports /tmp/falconops_branding \
    && chown -R falcon:falcon /app /tmp/falconops_reports /tmp/falconops_branding

# Copy pre-built site-packages from builder
COPY --from=builder /install /usr/local

# Grant CAP_NET_RAW on the interpreter binary itself (not just the container, via
# docker-compose's cap_add) so the non-root `falcon` user can open raw ICMP sockets
# for the network path analyzer's real traceroute — container-level cap_add alone
# doesn't reliably survive exec into a non-root process. Must run as root, on the
# real (symlink-resolved) ELF, before USER switches away from root.
RUN setcap cap_net_raw+ep "$(readlink -f "$(command -v python3.12)")"

# App code
COPY --chown=falcon:falcon . .

# Non-root execution
USER falcon

EXPOSE 8001

# Health probe — ECS target group also hits /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8001/api/health || exit 1

# Use 4 uvicorn workers in prod, tuned for Fargate 1vCPU / 2GB
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--log-level", "info", "--no-access-log"]
