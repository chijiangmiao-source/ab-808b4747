# Multi-stage image: build the React bundle, then serve it with nginx and
# proxy /api to the FastAPI service.
FROM node:20-alpine AS build
WORKDIR /app

COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=5s --timeout=3s --start-period=3s --retries=20 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
