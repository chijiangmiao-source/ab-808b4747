"""One-shot integration acceptance for docker compose service ``verify``.

Runs real HTTP requests against the API and the web container, prints a
human-readable report, and exits 0 only when every check passes.

Environment:
    API_BASE  default http://api:8000
    WEB_BASE  default http://web:80
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from fractions import Fraction

API_BASE = os.environ.get("API_BASE", "http://api:8000").rstrip("/")
WEB_BASE = os.environ.get("WEB_BASE", "http://web:80").rstrip("/")

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"[{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def request(method: str, url: str, payload=None, timeout: float = 30.0):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def wait_ready(url: str, attempts: int = 60, delay: float = 1.0) -> bool:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(delay)
    return False


def frac(d: dict) -> Fraction:
    return Fraction(d["num"], d["den"])


def main() -> int:
    print(f"== verify: API={API_BASE} WEB={WEB_BASE} ==")
    if not wait_ready(f"{API_BASE}/api/health"):
        print("API did not become healthy")
        return 2
    if not wait_ready(f"{WEB_BASE}/", attempts=60):
        print("WEB did not become ready")
        return 2

    status, body = request("GET", f"{API_BASE}/api/health")
    ok = status == 200 and json.loads(body).get("status") == "ok"
    record("API 健康检查 /api/health", ok, body.strip())

    # --- Case 1: exact rational point solution ---
    case1 = {
        "nodes": [10, 20, 30, 40],
        "edges": [
            {"u": 10, "v": 20, "length": 4},
            {"u": 20, "v": 30, "length": 6},
            {"u": 30, "v": 40, "length": 10},
        ],
        # truth: x=3 on edge #1 (20->30), t0=7
        "sensors": [
            {"node": 10, "time": 14},
            {"node": 20, "time": 10},
            {"node": 40, "time": 20},
        ],
    }
    status, body = request("POST", f"{API_BASE}/api/localize", case1)
    r = json.loads(body)
    ok = (
        status == 200
        and r.get("ok") is True
        and frac(r["result"]["optimal_value"]) == 0
        and r["result"]["canonical"]["edge_index"] == 1
        and frac(r["result"]["canonical"]["coordinate"]) == 3
        and frac(r["result"]["canonical"]["emission_time"]) == 7
    )
    record("精确点解：g*=0、规范源点 (管段#1, x=3, t0=7)", ok,
           f"g*={r.get('result', {}).get('optimal_value', {}).get('text')}")

    # --- Case 2: noisy data -> positive AND negative witnesses, half-open fractions ---
    case2 = {
        "nodes": [1, 2, 3, 4, 5],
        "edges": [
            {"u": 1, "v": 2, "length": 10},
            {"u": 1, "v": 3, "length": 6},
            {"u": 1, "v": 4, "length": 8},
            {"u": 1, "v": 5, "length": 12},
        ],
        "sensors": [
            {"node": 2, "time": 21},
            {"node": 3, "time": 16},
            {"node": 4, "time": 18},
            {"node": 5, "time": 23},
        ],
    }
    status, body = request("POST", f"{API_BASE}/api/localize", case2)
    r = json.loads(body)["result"]
    g = frac(r["optimal_value"])
    residuals = [frac(row["residual"]) for row in r["residuals"]]
    bound_ok = all(abs(x) <= g for x in residuals)
    pos, neg = r["witnesses"]["positive"], r["witnesses"]["negative"]
    witness_ok = bool(pos) and bool(neg) and all(frac(r["residuals"][i]["residual"]) == g for i in pos) \
        and all(frac(r["residuals"][i]["residual"]) == -g for i in neg)
    opt_order_ok = [o["edge_index"] for o in r["optima"]] == sorted(o["edge_index"] for o in r["optima"])
    record("含误差数据：全部 |残差| ≤ g*", bound_ok, f"g*={r['optimal_value']['text']}")
    record("最优性证据：正负极值传感器同时达到 ±g*", witness_ok, f"+:{pos} -:{neg}")
    record("同优位置按管段输入次序返回", opt_order_ok)

    # --- Case 3: closed-interval co-optimum ---
    case3 = {
        "nodes": [1, 2, 3, 4],
        "edges": [
            {"u": 1, "v": 2, "length": 10},
            {"u": 1, "v": 3, "length": 10},
            {"u": 1, "v": 4, "length": 10},
        ],
        "sensors": [{"node": 2, "time": 15}, {"node": 3, "time": 15}],
    }
    status, body = request("POST", f"{API_BASE}/api/localize", case3)
    r = json.loads(body)["result"]
    interval = next(o for o in r["optima"] if not o["point"])
    interval_ok = (
        frac(r["optimal_value"]) == 0
        and interval["edge_index"] == 2
        and frac(interval["coordinate_start"]) == 0
        and frac(interval["coordinate_end"]) == 10
        and interval["t0_segments"]
    )
    record("闭区间同优：无传感器支管 [0,10] 整段最优且给出 t0(x)", interval_ok,
           f"{interval['coordinate_start']['text']}..{interval['coordinate_end']['text']}")

    # --- Case 4: validation errors keep draft semantics and locate fields ---
    case4 = {
        "nodes": [1, 2, 3],
        "edges": [
            {"u": 1, "v": 2, "length": 4},
            {"u": 2, "v": 3, "length": 6},
            {"u": 1, "v": 3, "length": 2},
        ],
        "sensors": [
            {"node": 1, "time": 1},
            {"node": 9, "time": "abc"},
            {"node": 1, "time": 5},
        ],
    }
    status, body = request("POST", f"{API_BASE}/api/localize", case4)
    errs = json.loads(body).get("errors", [])
    keys = {(e["kind"], e["index"], e["field"]) for e in errs}
    located = ("sensor", 1, "node") in keys and ("sensor", 1, "time") in keys and ("sensor", 2, "node") in keys
    network_err = any(e["kind"] == "network" and "树" in e["message"] for e in errs)
    record("校验失败返回 422 并定位到行/字段（缺失引用、非整数、重复传感器）",
           status == 422 and located, f"{len(errs)} 个错误")
    record("无法成树（成环）被拒绝", status == 422 and network_err)

    # Out-of-range lengths rejected.
    case5 = {"nodes": [1, 2], "edges": [{"u": 1, "v": 2, "length": 0}],
             "sensors": [{"node": 1, "time": 0}, {"node": 2, "time": 1}]}
    status, _ = request("POST", f"{API_BASE}/api/localize", case5)
    record("长度 0（非正整数）被拒绝", status == 422)

    # --- Case 5: web container serves the React bundle and proxies the API ---
    status, index_html = request("GET", f"{WEB_BASE}/")
    serves_app = status == 200 and '<div id="root">' in index_html and "assets/" in index_html
    record("Web 提供已构建的 React 页面", serves_app)

    status, body = request("GET", f"{WEB_BASE}/api/health")
    proxied = status == 200 and json.loads(body).get("status") == "ok"
    record("经 Web 反代访问 /api/health 成功", proxied)

    status, body = request("POST", f"{WEB_BASE}/api/localize", case1)
    record("经 Web 反代完成真实定位联调", status == 200 and json.loads(body).get("ok") is True)

    # --- Case 6: maximum-size network (2000 nodes, 128 sensors) ---
    rng = random.Random(20260920)
    n = 2000
    big_nodes = list(range(1, n + 1))
    big_edges = [
        {"u": rng.randrange(v) + 1, "v": v + 1, "length": rng.randint(1, 100000)}
        for v in range(1, n)
    ]
    big_sensors = [
        {"node": s + 1, "time": rng.randint(-10 ** 6, 10 ** 6)}
        for s in rng.sample(range(n), 128)
    ]
    started = time.time()
    status, body = request("POST", f"{API_BASE}/api/localize",
                           {"nodes": big_nodes, "edges": big_edges, "sensors": big_sensors},
                           timeout=60)
    elapsed = time.time() - started
    r = json.loads(body).get("result", {})
    big_ok = status == 200 and r.get("node_count") == 2000 and r.get("sensor_count") == 128 \
        and isinstance(r.get("optima"), list) and r["optima"]
    record("极限规模 2000 节点 / 1999 管段 / 128 传感器求解成功", big_ok, f"{elapsed:.2f}s")

    print("\n== 验收汇总 ==")
    failed = [row for row in results if row[0] == FAIL]
    for status_name, name, detail in results:
        print(f"  [{status_name}] {name}" + (f" ({detail})" if detail and status_name == FAIL else ""))
    print(f"\n共 {len(results)} 项，失败 {len(failed)} 项")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
