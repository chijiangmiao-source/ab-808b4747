# 前端审计台（React 19 + Vite）

- `npm install`
- `npm run dev` 开发（已配置将 `/api`、`/health` 代理到 `http://127.0.0.1:8000`）
- `npm run build` 构建到 `dist/`，由 nginx 容器托管（见 `nginx.conf`）

功能与接口契约见仓库根目录 `README.md`。
