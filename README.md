# 树状管网声学泄漏定位审计台

地下储气库场景：声学传感器分布在树状管网的节点上，声源可位于任一管段的
连续位置，发声时刻未知且无先验。本项目提供从 React 编辑台到 FastAPI
精确求解器的全栈审计系统。

## 功能

- **草稿编辑**：在页面上增删节点、管段（正整数长度）和传感器（节点 +
  整数到达时刻），草稿自动保存在浏览器 `localStorage`，校验失败时**原样保留**。
- **精确定位错误**：无法成树、引用缺失、重复传感器、长度非正、数值越界等
  错误以 HTTP 422 返回，定位到具体的表行与字段并在输入框处红色高亮。
- **精确有理数求解**：后端全程使用 `fractions.Fraction`，最小化所有传感器
  预测时刻与观测时刻的**最大绝对残差**（L∞，发声时刻自由），坐标、发声
  时刻、残差均以 `num/den` 精确分数返回。
- **完整同优集合**：求出达到最优值的全部孤立点与闭区间；闭区间还给出区间
  内最优发声时刻 `t₀(x)` 的线性分段。
- **规范解**：按管段输入次序选取最早达到最优的管段，再取从其**首端 u**
  量起的最小坐标及对应发声时刻。
- **最优性证据**：残差表高亮达到 `+r*` 与 `−r*` 的传感器（悬停可在 SVG
  上联动），两者同时存在即证明 r* 无法再下降。
- **SVG 管网**：分层树布局，显示管段编号/长度、传感器、全部同优点/区间
  和规范源点。
- **规模**：支持 2–2000 个节点（恰好 n−1 条正整数长度管段构成树）、
  2–128 个位于不同节点的传感器。2000 节点/128 传感器求解约 0.1 s。

## 数学模型

波速归一化为 1。声源在管段 `(a,b)` 上、距首端 a 为 x 时，到节点 i 的距离
在树上是确定的；对传感器 i：

```
预测时刻 = t0 + distance(source, node_i)
残差 r_i(x, t0) = t_i − t0 − distance(source, node_i)
```

在单条管段上每个传感器的残差是 x 的斜率 ±1 的仿射函数（路径固定从管段的
某一端离开）。对固定 x，最优 t0 是残差中值，此时

```
r*(x) = (max_i r_i(x) − min_i r_i(x)) / 2
```

残差跨度 g(x) 是凸分段线性函数，其折线弯折点至多两个；枚举弯折点与端点
即可精确求出该管段上的全部最小集（点或闭区间）。遍历全部管段后取全局
最小值，并按上述规范确定唯一代表解。

## 目录结构

```
backend/
  app/solver.py       # 精确有理数求解器
  app/validation.py   # 草稿校验与错误定位
  app/main.py         # FastAPI：/api/health、/api/localize
  scripts/test_solver.py          # 400 组随机树数值对照测试
  scripts/verify_integration.py  # 一次性真实联调验收（退出码报告）
  scripts/dev_web_proxy.py       # 无 Docker 时的本地静态+反代替身
frontend/
  src/                # React + Vite：编辑器、SVG、结果面板
docker/nginx.conf     # Web 容器：托管静态资源并反代 /api
Dockerfile            # Web 多阶段镜像（node 构建 → nginx）
backend/Dockerfile    # API 镜像（uvicorn + 健康检查）
docker-compose.yml    # api / web / verify 三个服务
```

## 启动（Docker）

```bash
cp .env.example .env       # 可选：修改 WEB_HOST_PORT / API_HOST_PORT
docker compose up --build
```

- Web 审计台：http://localhost:${WEB_HOST_PORT:-8080}
- API 健康检查：http://localhost:${API_HOST_PORT:-8000}/api/health

宿主机端口通过环境变量配置，例如：

```bash
WEB_HOST_PORT=18080 API_HOST_PORT=18000 docker compose up --build
```

两个容器均带 `HEALTHCHECK`，`web` 与 `verify` 会等待 API 健康后启动。

## 一次性联调验收

```bash
docker compose run --rm verify
```

该服务对**真实运行中的 api 与 web 容器**发起 HTTP 请求，覆盖：健康检查、
精确点解（g*=0 且坐标/时刻正确）、含误差数据的正负极值证据、闭区间同优、
422 错误定位、非正长度拒绝、Web 页面托管、经 nginx 反代联调、2000 节点
极限规模。全部通过时退出码为 0，否则为 1（且容器打印逐项报告）。

## 本地开发（无 Docker）

```bash
# API
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Web（Vite 开发服务器，自动反代 /api）
cd frontend && npm install && npm run dev
```

后端可独立运行求解器属性测试（与密集数值采样对照）：

```bash
cd backend && python -m scripts.test_solver
```

## API

`POST /api/localize`

```json
{
  "nodes": [1, 2, 3, 4],
  "edges": [
    {"u": 1, "v": 2, "length": 10},
    {"u": 1, "v": 3, "length": 6}
  ],
  "sensors": [
    {"node": 2, "time": 21},
    {"node": 3, "time": 16}
  ]
}
```

成功返回 `{"ok": true, "result": {...}}`，其中每个有理数为
`{"num": 整数, "den": 正整数, "text": "a/b"}`；失败返回
`{"ok": false, "errors": [{"kind", "index", "field", "message"}]}`。
