"""Cross-check the exact solver against an independent half-integer grid.

With integer lengths/arrivals, every envelope crossing on an edge sits at a
half-integer coordinate, so a step-1/2 sweep over every edge exhaustively
finds the true minimax set. Run: python tests/test_solver.py
"""
import os
import random
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import solver  # noqa: E402
from app.solver import SolveError, solve  # noqa: E402

PASS = 0


def check(cond, msg):
    global PASS
    if not cond:
        raise AssertionError(msg)
    PASS += 1


def brute(payload):
    """Independent reference: sweep half-integer grid, return (R, set)."""
    edges = payload["edges"]
    sensors = payload["sensors"]
    # adjacency / all-pairs distances along the unique path
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"], e["length"]))
        adj.setdefault(e["to"], []).append((e["from"], e["length"]))

    def dist_point(edge, coord, node):
        # Dijkstra from the two endpoints would do, but tree: DFS distances
        def dfs_dist(src):
            dist = {src: 0}
            stack = [src]
            while stack:
                u = stack.pop()
                for w, L in adj[u]:
                    if w not in dist:
                        dist[w] = dist[u] + L
                        stack.append(w)
            return dist
        da = dfs_dist(edge["from"])
        return min(coord + da[node], (edge["length"] - coord) +
                   dfs_dist(edge["to"])[node])

    best = None
    best_set = set()
    for ei, e in enumerate(edges):
        k = 0
        while k <= 2 * e["length"]:
            z = Fraction(k, 2)
            fs = [s["arrival"] - dist_point(e, z, s["node"]) for s in sensors]
            width = Fraction(max(fs) - min(fs)) / 2
            key = (ei, z)
            if best is None or width < best:
                best = width
                best_set = {key}
            elif width == best:
                best_set.add(key)
            k += 1
    return best, best_set


def random_tree(rng, n, max_len=6):
    nodes = [f"v{i}" for i in range(n)]
    edges = []
    for i in range(1, n):
        j = rng.randrange(i)
        edges.append({"id": f"e{i}", "from": nodes[j], "to": nodes[i],
                      "length": rng.randint(1, max_len)})
    rng.shuffle(edges)
    return nodes, edges


def test_random(trials=400):
    rng = random.Random(20260921)
    for trial in range(trials):
        n = rng.randint(2, 8)
        nodes, edges = random_tree(rng, n)
        m = rng.randint(2, min(6, n))
        sensor_nodes = rng.sample(nodes, m)
        # synthetic emission: pick edge + fraction, t, then corrupt some
        if trial % 3 != 0:
            e = rng.choice(edges)
            coord = Fraction(rng.randint(0, 2 * e["length"]), 2)
            t0 = rng.randint(-3, 3)
            base = {"edges": edges, "sensors": []}
            adj = {}
            for x in edges:
                adj.setdefault(x["from"], []).append((x["to"], x["length"]))
                adj.setdefault(x["to"], []).append((x["from"], x["length"]))
            arrivals = []
            for sn in sensor_nodes:
                d = min(coord + dist_to(adj, e["from"], sn),
                        (e["length"] - coord) + dist_to(adj, e["to"], sn))
                arrivals.append(int(t0 + d) + (rng.randint(-1, 1)
                                               if trial % 2 else 0))
        else:
            arrivals = [rng.randint(0, 20) for _ in sensor_nodes]
        sensors = [{"id": f"s{i}", "node": sn, "arrival": a}
                   for i, (sn, a) in enumerate(zip(sensor_nodes, arrivals))]
        payload = {"edges": [dict(e) for e in edges], "sensors": sensors}

        res = solve(payload)
        R = Fraction(res["optimal_residual"]["n"],
                     res["optimal_residual"]["d"])
        bR, bset = brute(payload)
        check(R == bR, f"trial {trial}: R={R} brute={bR}")

        # every reported interval must cover exactly the brute grid points.
        # Physical points are compared: edge-interior grid points key by
        # (edge, coord), endpoints key by node id so the geometric union of
        # the solver's intervals matches the brute sweep despite dedup.
        def phys(ei, z):
            e = payload["edges"][ei]
            if z == 0:
                return ("node", e["from"])
            if z == e["length"]:
                return ("node", e["to"])
            return ("edge", ei, z)

        reported = set()
        for sol in res["solutions"]:
            ei = sol["edge_index"]
            lo = Fraction(sol["interval"]["start"]["n"],
                          sol["interval"]["start"]["d"])
            hi = Fraction(sol["interval"]["end"]["n"],
                          sol["interval"]["end"]["d"])
            k = 0
            while k <= 2 * payload["edges"][ei]["length"]:
                z = Fraction(k, 2)
                if lo <= z <= hi:
                    reported.add(phys(ei, z))
                k += 1
        check(reported == {phys(ei, z) for ei, z in bset},
              f"trial {trial}: optimal set mismatch\n solver={reported}\n"
              f" brute ={ {phys(ei, z) for ei, z in bset} }")

        # canonical rule: coordinate = smallest from-end coordinate (interval
        # low end); time = interval midpoint
        sol0 = res["solutions"][0]
        check(sol0["coordinate"]["n"] / sol0["coordinate"]["d"]
              == float(sol0["interval"]["start"]["n"])
              / sol0["interval"]["start"]["d"],
              f"trial {trial}: canonical coordinate not interval start")
        check(sorted(s["edge_index"] for s in res["solutions"])
              == [s["edge_index"] for s in res["solutions"]],
              "solutions not sorted by input edge order")

        # witnesses: + and - residual magnitude equals R, signs opposite
        for sol in res["solutions"]:
            check(sol["positive_witnesses"], f"trial {trial}: no + witness")
            check(sol["negative_witnesses"], f"trial {trial}: no - witness")
            for r in sol["sensor_residuals"]:
                rv = Fraction(r["residual"]["n"], r["residual"]["d"])
                check(abs(rv) <= R, "residual exceeds optimum")
                if r["sensor_id"] in sol["positive_witnesses"]:
                    check(rv == R, "positive witness not at +R")
                if r["sensor_id"] in sol["negative_witnesses"]:
                    check(rv == -R, "negative witness not at -R")
    print(f"random trials OK ({trials})")


def dist_to(adj, src, target):
    dist = {src: 0}
    stack = [src]
    while stack:
        u = stack.pop()
        for w, L in adj[u]:
            if w not in dist:
                dist[w] = dist[u] + L
                stack.append(w)
    return dist[target]


def test_known():
    # Straight path A--2--B--2--C, source at midpoint of AB, exact data.
    payload = {
        "edges": [
            {"id": "e1", "from": "A", "to": "B", "length": 2},
            {"id": "e2", "from": "B", "to": "C", "length": 2},
        ],
        "sensors": [
            {"id": "sA", "node": "A", "arrival": 1},
            {"id": "sC", "node": "C", "arrival": 3},
        ],
    }
    res = solve(payload)
    check(Fraction(res["optimal_residual"]["n"],
                   res["optimal_residual"]["d"]) == 0, "expected R=0")
    s0 = res["solutions"][0]
    check(s0["edge_id"] == "e1", "canonical edge should be first edge")
    check(Fraction(s0["coordinate"]["n"], s0["coordinate"]["d"]) == 1,
          "source coord 1 from A")
    check(Fraction(s0["time"]["n"], s0["time"]["d"]) == 0, "t=0")
    print("known exact case OK")


def test_interval():
    # Whole-edge flat optimum: A--4--B and A--1--C, sensors at A (t=0)
    # and C (arrival 1). On edge AB every point at emission time t=-z
    # explains both observations exactly (R=0), so the optimal set is the
    # entire closed edge [0, 4].
    payload = {
        "edges": [
            {"id": "e1", "from": "A", "to": "B", "length": 4},
            {"id": "e2", "from": "A", "to": "C", "length": 1},
        ],
        "sensors": [
            {"id": "x", "node": "A", "arrival": 0},
            {"id": "y", "node": "C", "arrival": 1},
        ],
    }
    res = solve(payload)
    sol = res["solutions"][0]
    R = Fraction(res["optimal_residual"]["n"], res["optimal_residual"]["d"])
    check(R == 0, f"R={R}, want 0")
    check(not sol["interval"]["degenerate"], "expected non-degenerate interval")
    lo = Fraction(sol["interval"]["start"]["n"], sol["interval"]["start"]["d"])
    hi = Fraction(sol["interval"]["end"]["n"], sol["interval"]["end"]["d"])
    check((lo, hi) == (0, 4), f"want full edge [0,4], got [{lo},{hi}]")
    check(sol["edge_id"] == "e1", "canonical: first input edge wins")
    check(Fraction(sol["coordinate"]["n"], sol["coordinate"]["d"]) == 0,
          "canonical coordinate is interval start")
    check(Fraction(sol["time"]["n"], sol["time"]["d"]) == 0,
          "canonical t at z=0 is 0")
    print("whole-edge optimal interval case OK")


def expect_error(payload, code):
    try:
        solve(payload)
    except SolveError as ex:
        check(any(e["code"] == code for e in ex.errors),
              f"want {code}, got {[e['code'] for e in ex.errors]}")
        return ex.errors
    raise AssertionError(f"expected error {code}")


def test_errors():
    good_edge = {"id": "e1", "from": "A", "to": "B", "length": 1}
    good_s = [{"id": "s1", "node": "A", "arrival": 0},
              {"id": "s2", "node": "B", "arrival": 1}]
    expect_error({"edges": [], "sensors": good_s}, "EDGES_MISSING")
    expect_error({"edges": [good_edge],
                  "sensors": [{"id": "s1", "node": "A", "arrival": 0}]},
                 "SENSOR_COUNT_INVALID")
    expect_error({"edges": [{**good_edge, "length": 0}], "sensors": good_s},
                 "LENGTH_NOT_POSITIVE")
    expect_error({"edges": [{**good_edge, "length": 1.5}],
                  "sensors": good_s}, "LENGTH_NOT_INTEGER")
    expect_error({"edges": [good_edge],
                  "sensors": [{"id": "s1", "node": "Z", "arrival": 0},
                              {"id": "s2", "node": "B", "arrival": 1}]},
                 "SENSOR_NODE_UNKNOWN")
    expect_error({"edges": [good_edge],
                  "sensors": [{"id": "s1", "node": "A", "arrival": 0},
                              {"id": "s2", "node": "A", "arrival": 1}]},
                 "SENSOR_NODE_DUPLICATE")
    expect_error({"edges": [good_edge,
                            {"id": "e2", "from": "B", "to": "C", "length": 1},
                            {"id": "e3", "from": "C", "to": "A", "length": 1}],
                  "sensors": [{"id": "s1", "node": "A", "arrival": 0},
                              {"id": "s2", "node": "B", "arrival": 1}]},
                 "TREE_CYCLE")
    expect_error({"edges": [good_edge,
                            {"id": "e2", "from": "C", "to": "D", "length": 1}],
                  "sensors": [{"id": "s1", "node": "A", "arrival": 0},
                              {"id": "s2", "node": "B", "arrival": 1}]},
                 "TREE_DISCONNECTED")
    expect_error({"edges": [{"id": "e0", "from": "A", "to": "A", "length": 1},
                            {"id": "e1", "from": "A", "to": "B", "length": 1}],
                  "sensors": good_s}, "TREE_SELF_LOOP")
    print("error cases OK")


def test_large():
    # 2000-node path and 128 sensors: must finish quickly, exact rationals.
    n = 2000
    edges = [{"id": f"e{i}", "from": f"v{i-1}", "to": f"v{i}",
              "length": 1 + (i % 7)} for i in range(1, n)]
    sensors = [{"id": f"s{i}", "node": f"v{15 * i}",
                "arrival": (15 * i) % 13 + i} for i in range(1, 129)]
    res = solve({"edges": edges, "sensors": sensors})
    check(res["status"] == "ok", "large solve failed")
    check(len(res["solutions"]) >= 1, "no solutions on large case")
    print(f"large case OK: R={res['optimal_residual']['dec']}")


if __name__ == "__main__":
    test_known()
    test_interval()
    test_errors()
    test_large()
    test_random()
    print(f"ALL CHECKS PASSED ({PASS} assertions)")
