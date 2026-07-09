# FalconOpsAI OneAgent — lightweight multi-stage build.
# Final image ~15MB, runs as non-root where possible.
FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" \
    -o /out/falconops-oneagent ./cmd/agent

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=build /out/falconops-oneagent /usr/local/bin/falconops-oneagent
COPY agent.yaml /etc/falconops/agent.yaml

# Host auto-detection: mount host /proc and / read-only and set HOST_PROC/HOST_ROOT.
#   docker run -d --name falconops-oneagent \
#     -e FALCONOPS_API_KEY=... -e FALCONOPS_BACKEND_URL=... \
#     -v /proc:/host/proc:ro -e HOST_PROC=/host/proc \
#     -v /var/log:/var/log:ro \
#     -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
#     --pid=host --network=host falconops/oneagent:latest

VOLUME ["/var/lib/falconops/buffer"]
ENTRYPOINT ["/usr/local/bin/falconops-oneagent"]
CMD ["--config", "/etc/falconops/agent.yaml"]
