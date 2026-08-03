# nexus-ai-engine-ui — Journey Studio SPA (spec 070)

FROM node:20-alpine AS builder
WORKDIR /app

RUN apk add --no-cache python3 make g++ && rm -rf /var/cache/apk/*

COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; \
    else npm install --no-audit --no-fund; fi

COPY tsconfig.json vite.config.ts vitest.config.ts tailwind.config.js postcss.config.js index.html ./
COPY src ./src

RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS production
USER root
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY VERSION /VERSION
RUN chown -R 10001:10001 /usr/share/nginx/html /etc/nginx/nginx.conf /VERSION
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
