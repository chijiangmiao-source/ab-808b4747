"""One-shot real end-to-end acceptance check (the ``verify`` compose service).

Runs entirely over HTTP against the running stack:

  web  -> http://web:80          (nginx serving the built React app and
                                  proxying /api to the API container)
  api  -> http://api:8000

Checks:
  1. health endpoints of both containers
  2. the built web app and its asset are served
  3. an exactly solvable case through the public nginx /api proxy:
     canonical point, emission time and rational values
  4. a case whose optimum set is a non-degenerate closed interval
  5. a branching case: optimum residual, positive/negative witness sensors
     and per-sensor residual bounds
  6. 422 validation with precise error codes/targets (cycle + bad node ref)
  7. a 500-node smoke case through the API

Exits 0 only if every check passes; prints a PASS/FAIL report.
"""
import os
import sys
import time

import httpx

WEB = os.getenv("VERIFY_WEB_URL", "http://web:80")
API = os.getenv("VERIFY_API_URL", "http://api:8000")
DEADLINE = float(os.getenv("VERIFY_DEADLINE", "60"))

failures = []
checks = 0


def check(cond, name, detail=""):
    global checks
    checks += 1
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(f"{name}: {detail}")


def wait_ready(client, url, name):
    deadline = time.time() + DEADLINE
    last = ""
    while time.time() < deadline:
        try:
            r = client.get(url, timeout=3)
            if r.status_code == 200:
                print(f"[READY] {name} ({url})")
                return True
            last = f"HTTP {r.status_code}"
        except Exception as ex:
            last = str(ex)
        time.sleep(1)
    print(f"[TIMEOUT] {name} never became ready: {last}")
    return False


def frac(f):
    from fractions import Fraction
    return Fraction(f["n"], f["d"])


def main():
    with httpx.Client(timeout=30) as client:
        if not wait_ready(client, f"{API}/health", "api"):
            return 2
        if not wait_ready(client, f"{WEB}/", "web"):
            return 2

        # 1. health bodies
        r = client.get(f"{API}/health")
        check(r.status_code == 200 and r.json()["status"] == "healthy",
              "api /health body", r.text)
        r = client.get(f"{WEB}/health")
        check(r.status_code == 200 and r.json()["status"] == "healthy",
              "web -> api /health proxy", r.text)

        # 2. built app is served by nginx
        r = client.get(f"{WEB}/")
        body = r.text
        check(r.status_code == 200 and '<div id="root"></div>' in body,
              "web serves React index.html")
        asset = None
        for line in body.splitlines():
            if "/assets/index-" in line and line.strip().endswith(".js"):
                pass
            if 'src="/assets/' in line:
                asset = line.split('src="')[1].split('"')[0]
        check(asset is not None, "index.html references built JS asset", body[:200])
        if asset:
            r = client.get(f"{WEB}{asset}")
            check(r.status_code == 200 and len(r.content) > 1000,
                  f"built JS asset reachable ({asset})")

        # 3. exact case through the PUBLIC proxy path
        exact = {
            "edges": [
                {"id": "e1", "from": "A", "to": "B", "length": 2},
                {"id": "e2", "from": "B", "to": "C", "length": 2},
            ],
            "sensors": [
                {"id": "sA", "node": "A", "arrival": 1},
                {"id": "sC", "node": "C", "arrival": 3},
            ],
        }
        r = client.post(f"{WEB}/api/v1/locate", json=exact)
        check(r.status_code == 200, "exact case HTTP 200 via nginx", r.text)
        if r.status_code == 200:
            d = r.json()
            check(frac(d["optimal_residual"]) == 0, "exact case R*=0",
                  d["optimal_residual"]["dec"])
            s0 = d["solutions"][0]
            check(s0["edge_id"] == "e1" and frac(s0["coordinate"]) == 1
                  and frac(s0["time"]) == 0,
                  "canonical source e1@1 from A, t=0",
                  f'{s0["edge_id"]}@{s0["coordinate"]["dec"]} t={s0["time"]["dec"]}')
            check(s0["interval"]["degenerate"], "exact solution is a single point")

        # 4. whole-edge optimal closed interval
        interval = {
            "edges": [
                {"id": "e1", "from": "A", "to": "B", "length": 4},
                {"id": "e2", "from": "A", "to": "C", "length": 1},
            ],
            "sensors": [
                {"id": "x", "node": "A", "arrival": 0},
                {"id": "y", "node": "C", "arrival": 1},
            ],
        }
        r = client.post(f"{API}/api/v1/locate", json=interval)
        d = r.json()
        check(r.status_code == 200, "interval case HTTP 200", r.text)
        s0 = d["solutions"][0]
        check(frac(d["optimal_residual"]) == 0
              and frac(s0["interval"]["start"]) == 0
              and frac(s0["interval"]["end"]) == 4
              and not s0["interval"]["degenerate"],
              "optimum set is full edge [0,4]", str(s0["interval"]))

        # 5. branching minimax case with witnesses on both sides
        branch = {
            "edges": [
                {"id": "e3", "from": "v2", "to": "v3", "length": 3},
                {"id": "e4", "from": "v2", "to": "v4", "length": 2},
                {"id": "e2", "from": "v0", "to": "v2", "length": 6},
                {"id": "e1", "from": "v0", "to": "v1", "length": 4},
            ],
            "sensors": [
                {"id": "s0", "node": "v1", "arrival": 16},
                {"id": "s1", "node": "v2", "arrival": 4},
                {"id": "s2", "node": "v3", "arrival": 3},
                {"id": "s3", "node": "v4", "arrival": 8},
                {"id": "s4", "node": "v0", "arrival": 10},
            ],
        }
        r = client.post(f"{API}/api/v1/locate", json=branch)
        d = r.json()
        R = frac(d["optimal_residual"])
        check(R == 1, "branching case R*=1", d["optimal_residual"]["dec"])
        s0 = d["solutions"][0]
        check(s0["edge_id"] == "e3"
              and frac(s0["interval"]["start"]) == 2
              and frac(s0["interval"]["end"]) == 3,
              "branching optimal interval e3 [2,3] measured from v2",
              str(s0["interval"]))
        by_id = {x["sensor_id"]: x for x in s0["sensor_residuals"]}
        pos, neg = set(s0["positive_witnesses"]), set(s0["negative_witnesses"])
        check(bool(pos) and bool(neg), "both witness sides present",
              f"+{pos} -{neg}")
        ok_wit = all(frac(by_id[p]["residual"]) == R for p in pos) and \
                 all(frac(by_id[n]["residual"]) == -R for n in neg)
        check(ok_wit, "witness residuals are exactly +R* and -R*",
              f"+{sorted(pos)} -{sorted(neg)} R={R}")
        ok_bounds = all(abs(frac(x["residual"])) <= R
                        for x in s0["sensor_residuals"])
        check(ok_bounds, "every |residual| <= R*")

        # 6. validation: precise errors, draft-safe 422
        bad = {
            "edges": [
                {"id": "e1", "from": "A", "to": "B", "length": 1},
                {"id": "e2", "from": "B", "to": "C", "length": 1},
            ],
            "sensors": [
                {"id": "s1", "node": "A", "arrival": 0},
                {"id": "s2", "node": "ZZ", "arrival": "x"},
            ],
        }
        r = client.post(f"{API}/api/v1/locate", json=bad)
        check(r.status_code == 422, "invalid case returns 422", str(r.status_code))
        codes = {e["code"] for e in r.json()["errors"]}
        check({"SENSOR_NODE_UNKNOWN", "ARRIVAL_NOT_INTEGER"} <= codes,
              "error codes include unknown node / non-integer arrival",
              str(sorted(codes)))
        targeted = [e for e in r.json()["errors"] if e.get("sensor_index") == 1]
        check(len(targeted) >= 2, "errors located to row/cell targets",
              str(r.json()["errors"]))

        # cycle is a structural error and needs a field-valid payload
        cyclic = {
            "edges": [
                {"id": "e1", "from": "A", "to": "B", "length": 1},
                {"id": "e2", "from": "B", "to": "C", "length": 1},
                {"id": "e3", "from": "C", "to": "A", "length": 1},
            ],
            "sensors": [
                {"id": "s1", "node": "A", "arrival": 0},
                {"id": "s2", "node": "B", "arrival": 1},
            ],
        }
        r = client.post(f"{API}/api/v1/locate", json=cyclic)
        check(r.status_code == 422 and "TREE_CYCLE"
              in {e["code"] for e in r.json()["errors"]},
              "cyclic graph returns 422 TREE_CYCLE located to the edge",
              r.text)
        cyc_err = next((e for e in r.json()["errors"]
                        if e["code"] == "TREE_CYCLE"), {})
        check(cyc_err.get("edge_index") == 2,
              "cycle error targets the closing edge e3", str(cyc_err))

        r = client.post(f"{API}/api/v1/locate", json={"edges": [], "sensors": []})
        check(r.status_code == 422
              and {e["code"] for e in r.json()["errors"]}
              == {"EDGES_MISSING", "SENSORS_MISSING"},
              "empty lists rejected with both codes")

        # 7. 500-node smoke through the API
        n = 500
        big = {
            "edges": [{"id": f"e{i}", "from": f"v{i-1}", "to": f"v{i}",
                       "length": 1 + (i % 7)} for i in range(1, n)],
            "sensors": [{"id": f"s{i}", "node": f"v{5 * i}",
                         "arrival": i * 3 + (i % 5)} for i in range(1, 65)],
        }
        r = client.post(f"{API}/api/v1/locate", json=big)
        check(r.status_code == 200, "500-node / 64-sensor case HTTP 200",
              r.text[:300])
        if r.status_code == 200:
            d = r.json()
            check(d["node_count"] == n and d["solution_count"] >= 1,
                  "500-node case solved with >=1 solution",
                  f'R*={d["optimal_residual"]["dec"]}')

    print(f"\n{checks} checks, {len(failures)} failures")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("ACCEPTANCE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
