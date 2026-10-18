# syntax=docker/dockerfile:1
# ---- stage 1: build the static bundle --------------------------------------
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

# ---- stage 2: serve it with unprivileged nginx -----------------------------
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime

# Drop dynamic modules we never load: they drag in libtiff/libxslt/geoip and
# their CVEs. Then pick up any patched Alpine packages.
USER root
RUN apk del --no-cache nginx-module-image-filter nginx-module-xslt nginx-module-geoip nginx-module-njs 2>/dev/null || true \
 && apk upgrade --no-cache
USER 101

ENV BACKEND_URL=http://backend:8000
COPY --chown=101:101 nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build --chown=101:101 /src/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
