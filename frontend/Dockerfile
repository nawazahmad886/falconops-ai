# ─────────────────────────────────────────────────────────────────────────────
# FalconOps AI — Frontend production image
# Multi-stage: build React app with `yarn build` → serve via nginx
#
# IMPORTANT: REACT_APP_BACKEND_URL is BAKED into the JS at build time. To change
# it, rebuild with --build-arg REACT_APP_BACKEND_URL=https://your-host.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# Accept the backend URL as a build arg so docker-compose can pass it.
# Default works for the bundled docker-compose (nginx on port 80).
ARG REACT_APP_BACKEND_URL=http://localhost
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
# Disable ESLint dev errors so a CI build doesn't fail on lint warnings
ENV ESLINT_NO_DEV_ERRORS=true
ENV DISABLE_ESLINT_PLUGIN=true
# Source maps disabled in prod to keep the image small
ENV GENERATE_SOURCEMAP=false

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000

COPY . .
RUN yarn build

# ─────────────────────────────────────────────────────────────────────────────
# Production runtime — tiny nginx serving the built static files
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000

# Quick health check — nginx 200 on /
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
