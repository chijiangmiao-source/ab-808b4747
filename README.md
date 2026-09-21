# 树状管网泄漏定位审计台

分布在树状管网上的声学传感器，在**未知发声时刻**的情况下定位泄漏源。
分叉处逐传感器回推会给出互相矛盾的位置；本系统以**精确有理数**最小化
所有传感器预测时刻与观测时刻的**最大绝对残差**（L∞ / minimax），并完整求出
达到最优值的全部点或闭区间。

## 数学模型

声速归一化为 1。声源位于管段上距首端 `z` 处，发声时刻为 `t`：

```
pred_i(z,t) = t + dist(source(z), sensor_i)
residual_i  = observed_i − pred_i
```

固定位置 `z` 时，令 `f_i(z) = observed_i − dist_i(z)`，则使最大绝对残差最小的
发声时刻区间为 `[min_i f_i(z), max_i f_i(z)]`，该位置的最优残差为

```
R(z) = (max_i f_i(z) − min_i f_i(z)) / 2
```

在树中把管段定向为「根侧端点 u → 子节点 v」，参数 `z` 为距 u 的距离：

- 子树内传感器：`f_i(z) = const + z`（斜率 +1）
- 子树外传感器：`f_i(z) = const − z`（斜率 −1）

树的度量保证每条 `f_i` 在**管段内部无拐点**，因此上下包络各至多由两条直线
构成，两包络之差的最优集是一个（可退化的）**闭区间**。全部计算使用
Python `fractions.Fraction`，无浮点误差；解按

1. 管段输入次序，
2. 自首端量起的坐标（区间最小元），
3. 规范发声时刻（该点可行区间的中点），

排序，首个解即**规范源点**。相邻管段在共享节点处的重复退化解按几何位置去重。

## 目录结构

```
backend/
  app/solver.py    精确有理数 minimax 内核（校验、建树、LCA、区间求解）
  app/main.py      FastAPI：/health、/api/v1/locate、/api/v1/limits
  tests/test_solver.py  400 随机树 × 独立半整数网格枚举交叉验证
  verify.py        一次性真实联调验收（通过 web 反代打真实 HTTP 接口）
  Dockerfile / Dockerfile.verify
frontend/
  src/             React 19：管段/传感器编辑、错误定位、SVG 管网、结果与残差
  nginx.conf       托管构建产物并把 /api、/health 反代到 api 容器
  Dockerfile
docker-compose.yml  api / web / verify 三个服务
scripts/local_verify.sh  无 Docker 时的等价本机联调脚本
```

## 使用 Docker Compose

```bash
cp .env.example .env          # 可选：修改宿主机端口
docker compose build
docker compose up -d
# 打开 http://localhost:8080
```

- `WEB_HOST_PORT`（默认 8080）：Web 审计台宿主机端口
- `API_HOST_PORT`（默认 8000）：直接暴露的 FastAPI 端口
- `web` 与 `api` 均带 HEALTHCHECK；`web` 仅在 `api` 健康后启动

### 一次性联调验收服务 verify

完成真实联调后**自行退出**，并以退出码报告结果（0 = 全部通过）：

```bash
docker compose run --rm verify; echo "exit=$?"
```

它依次验证：健康检查、构建产物可达、精确解、整段同优闭区间、分叉算例的
正/负极值传感器（最优性证据）与各传感器残差、422 错误精确定位（成环边、
缺失节点引用、非整数时刻）、500 节点/64 传感器算例。

### 无 Docker 环境

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)
scripts/local_verify.sh       # 启动真实 uvicorn + 静态反代并跑 verify
# 或分别启动：
(cd backend && ../.venv/bin/uvicorn app.main:app --port 8000)
(cd frontend && npm run dev)  # vite dev 下可设置 VITE_API_BASE
```

## API

`POST /api/v1/locate`

```json
{
  "edges":   [{"id":"e1","from":"A","to":"B","length":2}],
  "sensors": [{"id":"s1","node":"A","arrival":1}]
}
```

约束：2–2000 个节点；管段为正整数长度（≤10⁹）且恰好构成一棵树；
2–128 个传感器位于**不同**且存在的节点；到达时刻为整数（|a|≤10¹²）。
成功返回 `optimal_residual`（分子/分母/十进制）与 `solutions`：每条包含
规范坐标、同优闭区间 `[start,end]`、发声时刻、达到 `+R*` / `−R*` 的
传感器 id，以及全部传感器的精确预测时刻与残差。
任何校验失败返回 `422 {"status":"error","errors":[...]}`，错误带
`edge_index`/`sensor_index`/`field`/`target`，前端据此定位到具体单元格，
**草稿始终保留**。

## 前端

- 管段/传感器表格式编辑，内容实时存入 `localStorage`，校验失败不丢草稿
- SVG 管网按深度与累计管长布局；红边=同优管段，加粗段=同优闭区间，
  黄点=规范源点，蓝色节点=传感器
- 结果面板：R*、全部同优位置页签、正/负极值证人、逐传感器残差表
