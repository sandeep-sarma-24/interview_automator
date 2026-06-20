# syntax=docker/dockerfile:1
# Multi-stage build: Node (build SPA) → nginx (serve static + reverse proxy).
# Produces a ~25 MB image with only the compiled assets + nginx.

# ───────────────────────────── build ─────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi

COPY . .
RUN npm run build          # tsc -b && vite build → /app/dist

# ───────────────────────────── runtime ─────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
