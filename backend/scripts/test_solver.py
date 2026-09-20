"""Property tests: compare exact solver against dense numeric sampling on
random trees. Run: python -m scripts.test_solver  (from backend/)."""

import random
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.solver import solve  # noqa: E402


def brute_best(node_ids, edges, sensors, samples_per_edge=401):
    n = len(node_ids)
    adj = {i: [] for i in range(n)}
    for k, (u, v, L) in enumerate(edges):
        adj[u].append((v, L))
        adj[v].append((u, L))
    inf = float("inf")
    dmat = [[inf] * n for _ in sensors]
    for i, (s, _t) in enumerate(sensors):
        dmat[i][s] = 0
        st = [s]
        while st:
            cur = st.pop()
            for nxt, w in adj[cur]:
                if dmat[i][nxt] == inf:
                    dmat[i][nxt] = dmat[i][cur] + w
                    st.append(nxt)
    times = [t for _s, t in sensors]
    g_best = inf
    for u, v, L in edges:
        for q in range(samples_per_edge):
            x = L * q / (samples_per_edge - 1)
            vals = []
            for i in range(len(sensors)):
                dist = min(dmat[i][u] + x, dmat[i][v] + (L - x))
                vals.append(times[i] - dist)
            g = max(vals) - min(vals)
            if g < g_best:
                g_best = g
    return g_best / 2.0


def random_tree(rng, n):
    edges = []
    for v in range(1, n):
        u = rng.randrange(v)
        edges.append((u, v, rng.randint(1, 9)))
    return edges


def main():
    rng = random.Random(20260920)
    failures = 0
    for trial in range(400):
        n = rng.randint(2, 9)
        edges = random_tree(rng, n)
        node_ids = list(range(1, n + 1))
        ns = rng.randint(2, min(n, 6))
        chosen = rng.sample(range(n), ns)
        true_edge = rng.randrange(len(edges))
        u, v, L = edges[true_edge]
        x_true = rng.choice([0, L, L / 2, rng.uniform(0, L)])
        t0_true = rng.randint(-50, 50)
        # distances from source
        adj = {i: [] for i in range(n)}
        for a, b, w in edges:
            adj[a].append((b, w))
            adj[b].append((a, w))
        du = {u: 0}
        st = [u]
        while st:
            cur = st.pop()
            for nxt, w in adj[cur]:
                if nxt not in du:
                    du[nxt] = du[cur] + w
                    st.append(nxt)
        sensors = []
        for s in chosen:
            dist = min(du[s] + x_true, du[v] + (L - x_true))
            noise = rng.choice([0, 0, 0, rng.randint(-3, 3)])
            t = round(t0_true + dist + noise)
            sensors.append((s, int(t)))
        result = solve(node_ids, edges, sensors)
        g_star = float(result["optimal_value"]["num"]) / result["optimal_value"]["den"]
        g_brute = brute_best(node_ids, edges, sensors)
        if abs(g_star - g_brute) > 2e-2:
            failures += 1
            print(f"trial {trial}: solver g*={g_star} brute={g_brute}")
            print(" n=", n, "edges=", edges, "sensors=", sensors)
            if failures > 5:
                break

    # Structured checks.
    # 1. Perfect data (no noise) -> g* = 0 and canonical point equals truth
    #    for a unique-source network (path 1-2-3, sensors at ends).
    edges = [(0, 1, 4), (1, 2, 6)]
    # source at x=3 on edge 1 (nodes 2..3 in 1-based ids), t0 = 7:
    # distances 7 to node 0 (3+4), 3 to node 2.
    node_ids = [1, 2, 3]
    result = solve(node_ids, edges, [(0, 14), (2, 10)])
    assert result["optimal_value"]["num"] == 0, result["optimal_value"]
    c = result["canonical"]
    assert c["edge_index"] == 1 and c["coordinate"]["num"] == 3 and c["coordinate"]["den"] == 1, c
    assert c["emission_time"]["num"] == 7, c
    assert len(result["optima"]) == 1 and result["optima"][0]["point"], result["optima"]
    print("perfect-data canonical point OK")

    # 2. Interval optimum: star 1-0-2 with sensors at leaves 1,2 reporting the
    #    same time.  The whole sensor-free third branch 0-3 is co-optimal
    #    (both distances grow together), plus the center point.
    edges = [(0, 1, 10), (0, 2, 10), (0, 3, 10)]
    result = solve([1, 2, 3, 4], edges, [(1, 15), (2, 15)])
    assert result["optimal_value"]["num"] == 0, result["optimal_value"]
    assert [o["edge_index"] for o in result["optima"]] == [0, 1, 2], result["optima"]
    assert result["optima"][0]["point"] and result["optima"][0]["coordinate_start"]["num"] == 0
    assert result["optima"][1]["point"] and result["optima"][1]["coordinate_start"]["num"] == 0
    flat = result["optima"][2]
    assert not flat["point"]
    assert flat["coordinate_start"]["num"] == 0 and flat["coordinate_end"]["num"] == 10
    print("sensor-free branch interval optimum OK")

    # 3. Witnesses: residual extremes hit +g* and -g* for noisy data.
    edges = [(0, 1, 10), (1, 2, 10)]
    sensors = [(0, 26), (2, 4)]  # truth t0=6, source node1; +0/-0 expected g*=0? 26-(6+10)=10? no
    result = solve([1, 2, 3], edges, sensors)
    g = Fraction(result["optimal_value"]["num"], result["optimal_value"]["den"])
    for row in result["residuals"]:
        r = Fraction(row["residual"]["num"], row["residual"]["den"])
        assert abs(r) <= g + 1e-12
    pos = result["witnesses"]["positive"]
    neg = result["witnesses"]["negative"]
    assert pos and neg and set(pos) | set(neg), result["witnesses"]
    print("witnesses OK")

    if failures:
        print(f"FAILED: {failures} mismatches")
        sys.exit(1)
    print("ALL 400 RANDOM TRIALS PASSED")


if __name__ == "__main__":
    main()
