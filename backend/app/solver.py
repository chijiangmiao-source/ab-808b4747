"""Exact rational minimax leak localization on a tree-shaped pipe network.

Model (signal speed normalized to 1):
    predicted arrival of sensor i : t + dist(source, sensor_i)
    residual_i                     : a_i - (t + dist_i)

For a fixed source point on an edge, the feasible emission times satisfy
    L <= t <= U,  where
    U(z) = max_i f_i(z) = -min residual contribution,
    L(z) = min_i f_i(z),  f_i(z) = a_i - dist_i(z).
The minimax residual at that point is R(z) = (U(z) - L(z)) / 2.

Root the tree at one node. For an edge with root-side endpoint u and child v
(length ell), parameterize a point by z = distance from u along the edge:
  * sensor s in the subtree of v: dist = (H[s] - H[u]) - z   (slope +1 line)
  * sensor s outside subtree(v): dist = dist(u, s) + z        (slope -1 line)
Thus U and L on the open edge are each the max/min of at most two straight
lines (one per slope class). Their crossings clamp to a closed interval on
which U - L is constant and globally minimal for that edge. Every fraction
is computed exactly with :mod:`fractions`.
"""

from __future__ import annotations

from fractions import Fraction
from math import log2, ceil

MAX_NODES = 2000
MIN_NODES = 2
MAX_SENSORS = 128
MIN_SENSORS = 2
MAX_LENGTH = 1_000_000_000
MAX_ABS_ARRIVAL = 10**12
MAX_ID_LEN = 64


def frac_json(value: Fraction) -> dict:
    return {"n": value.numerator, "d": value.denominator, "dec": _decimal(value)}


def _decimal(value: Fraction) -> str:
    # Exact or parenthesized repeating/long expansion; float gives a quick view.
    sign = "-" if value < 0 else ""
    v = abs(value)
    q, r = divmod(v.numerator, v.denominator)
    if r == 0:
        return f"{sign}{q}"
    digits = []
    seen = {}
    while r and r not in seen:
        seen[r] = len(digits)
        r *= 10
        digits.append(str(r // v.denominator))
        r %= v.denominator
    if r == 0:
        return f"{sign}{q}.{''.join(digits)}"
    start = seen[r]
    nonrep = "".join(digits[:start])
    rep = "".join(digits[start:])
    return f"{sign}{q}.{nonrep}({rep})"


class SolveError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


def _err(code, message, *, edge_index=None, sensor_index=None, field=None):
    e = {"code": code, "message": message}
    if edge_index is not None:
        e["edge_index"] = edge_index
    if sensor_index is not None:
        e["sensor_index"] = sensor_index
    if field is not None:
        e["field"] = field
    target = ""
    if edge_index is not None:
        target = f"edges[{edge_index}]"
    elif sensor_index is not None:
        target = f"sensors[{sensor_index}]"
    if field:
        target = f"{target}.{field}" if target else field
    if target:
        e["target"] = target
    return e


def validate_input(payload):
    errors: list[dict] = []

    if not isinstance(payload, dict):
        raise SolveError([_err("BAD_REQUEST", "请求体必须是 JSON 对象")])

    raw_edges = payload.get("edges")
    raw_sensors = payload.get("sensors")
    if not isinstance(raw_edges, list) or not raw_edges:
        errors.append(_err("EDGES_MISSING", "edges 必须是非空数组", field="edges"))
        raw_edges = []
    if not isinstance(raw_sensors, list) or not raw_sensors:
        errors.append(_err("SENSORS_MISSING", "sensors 必须是非空数组", field="sensors"))
        raw_sensors = []
    if errors:
        raise SolveError(errors)

    edges = []
    node_set: set[str] = set()
    seen_edge_ids: set[str] = set()

    for i, e in enumerate(raw_edges):
        if not isinstance(e, dict):
            errors.append(_err("EDGE_NOT_OBJECT", "管段必须是对象", edge_index=i))
            continue
        eid = e.get("id") or f"E{i + 1}"
        a = e.get("from")
        b = e.get("to")
        length = e.get("length")
        ok = True
        if not isinstance(eid, str) or not eid.strip() or len(eid) > MAX_ID_LEN:
            errors.append(_err("EDGE_ID_INVALID", f"管段 id 非法（长度 1–{MAX_ID_LEN}）",
                               edge_index=i, field="id"))
            ok = False
        elif eid in seen_edge_ids:
            errors.append(_err("EDGE_ID_DUPLICATE", f"管段 id {eid!r} 重复",
                               edge_index=i, field="id"))
            ok = False
        if not isinstance(a, str) or not a.strip():
            errors.append(_err("NODE_REF_INVALID", "管段首端节点缺失或非法",
                               edge_index=i, field="from"))
            ok = False
            a = None
        if not isinstance(b, str) or not b.strip():
            errors.append(_err("NODE_REF_INVALID", "管段末端节点缺失或非法",
                               edge_index=i, field="to"))
            ok = False
            b = None
        if isinstance(length, bool) or not isinstance(length, int):
            errors.append(_err("LENGTH_NOT_INTEGER", "管段长度必须是整数",
                               edge_index=i, field="length"))
            ok = False
        elif length < 1:
            errors.append(_err("LENGTH_NOT_POSITIVE", "管段长度必须为正整数",
                               edge_index=i, field="length"))
            ok = False
        elif length > MAX_LENGTH:
            errors.append(_err("LENGTH_OUT_OF_RANGE",
                               f"管段长度超出允许范围 (1..{MAX_LENGTH})",
                               edge_index=i, field="length"))
            ok = False
        if a is not None and len(a) > MAX_ID_LEN:
            errors.append(_err("NODE_REF_INVALID", f"节点名长度超过 {MAX_ID_LEN}",
                               edge_index=i, field="from"))
            ok = False
        if b is not None and len(b) > MAX_ID_LEN:
            errors.append(_err("NODE_REF_INVALID", f"节点名长度超过 {MAX_ID_LEN}",
                               edge_index=i, field="to"))
            ok = False
        if ok:
            seen_edge_ids.add(eid)
            edges.append({"id": eid, "from": a, "to": b, "length": length,
                          "input_index": i})
            node_set.add(a)
            node_set.add(b)

    n = len(node_set)
    if not errors:
        if n < MIN_NODES:
            errors.append(_err("NODE_COUNT_INVALID",
                               f"节点数必须在 {MIN_NODES}..{MAX_NODES} 之间（当前 {n}）",
                               field="edges"))
        elif n > MAX_NODES:
            errors.append(_err("NODE_COUNT_INVALID",
                               f"节点数必须在 {MIN_NODES}..{MAX_NODES} 之间（当前 {n}）",
                               field="edges"))

    sensors = []
    sensor_nodes: set[str] = set()
    seen_sensor_ids: set[str] = set()
    if not (MIN_SENSORS <= len(raw_sensors) <= MAX_SENSORS):
        errors.append(_err("SENSOR_COUNT_INVALID",
                           f"传感器数量必须在 {MIN_SENSORS}..{MAX_SENSORS} 之间"
                           f"（当前 {len(raw_sensors)}）", field="sensors"))
    for j, s in enumerate(raw_sensors):
        if not isinstance(s, dict):
            errors.append(_err("SENSOR_NOT_OBJECT", "传感器必须是对象", sensor_index=j))
            continue
        sid = s.get("id")
        node = s.get("node")
        arrival = s.get("arrival")
        ok = True
        if not isinstance(sid, str) or not sid.strip() or len(sid) > MAX_ID_LEN:
            errors.append(_err("SENSOR_ID_INVALID", f"传感器 id 非法（长度 1–{MAX_ID_LEN}）",
                               sensor_index=j, field="id"))
            ok = False
        elif sid in seen_sensor_ids:
            errors.append(_err("SENSOR_ID_DUPLICATE", f"传感器 id {sid!r} 重复",
                               sensor_index=j, field="id"))
            ok = False
        if not isinstance(node, str) or not node.strip():
            errors.append(_err("SENSOR_NODE_MISSING", "传感器所在节点缺失",
                               sensor_index=j, field="node"))
            ok = False
            node = None
        elif node not in node_set:
            errors.append(_err("SENSOR_NODE_UNKNOWN",
                               f"传感器引用了不存在的节点 {node!r}",
                               sensor_index=j, field="node"))
            ok = False
        elif node in sensor_nodes:
            errors.append(_err("SENSOR_NODE_DUPLICATE",
                               f"节点 {node!r} 上已有传感器（传感器须位于不同节点）",
                               sensor_index=j, field="node"))
            ok = False
        if isinstance(arrival, bool) or not isinstance(arrival, int):
            errors.append(_err("ARRIVAL_NOT_INTEGER", "到达时刻必须是整数",
                               sensor_index=j, field="arrival"))
            ok = False
        elif abs(arrival) > MAX_ABS_ARRIVAL:
            errors.append(_err("ARRIVAL_OUT_OF_RANGE",
                               f"到达时刻超出允许范围 (±{MAX_ABS_ARRIVAL})",
                               sensor_index=j, field="arrival"))
            ok = False
        if ok:
            seen_sensor_ids.add(sid)
            sensor_nodes.add(node)
            sensors.append({"id": sid, "node": node, "arrival": arrival,
                            "input_index": j})

    if errors:
        raise SolveError(errors)
    return edges, sensors, sorted(node_set), n


def build_tree(edges, nodes):
    """Root the tree; return per-node / per-edge topology data or raise.

    Connectedness, cycles and self-loops are all detected by one DFS:
    a connected simple graph on n nodes is a tree iff it has no cycle,
    and a graph with too few edges cannot be connected.
    """
    n = len(nodes)
    index = {v: i for i, v in enumerate(nodes)}
    adj = [[] for _ in range(n)]
    for ei, e in enumerate(edges):
        a, b = index[e["from"]], index[e["to"]]
        if a == b:
            raise SolveError([_err("TREE_SELF_LOOP",
                                   f"管段 {e['id']} 首尾节点相同，不能构成树",
                                   edge_index=ei, field="to")])
        adj[a].append((b, ei))
        adj[b].append((a, ei))

    # Root = first endpoint of the first edge in input order (appears first
    # in ``nodes`` first-appearance order would also work; keep deterministic).
    root = index[edges[0]["from"]]
    parent = [-1] * n
    parent_edge = [-1] * n
    depth_edges = [0] * n
    height = [0] * n  # total pipe length from root
    tin = [0] * n
    tout = [0] * n
    order = []
    parent[root] = root
    stack = [(root, -1, 0)]  # node, parent, entry phase
    timer = 0
    visited = [False] * n
    # iterative DFS with enter/exit for subtree intervals
    dfs_stack = [(root, -1, 0)]  # (node, from_edge, child_cursor)
    visited[root] = True
    tin[root] = timer
    timer += 1
    while dfs_stack:
        u, pe, cursor = dfs_stack[-1]
        if cursor < len(adj[u]):
            w, ei = adj[u][cursor]
            dfs_stack[-1] = (u, pe, cursor + 1)
            if ei == pe:
                continue
            if visited[w]:
                e = edges[ei]
                raise SolveError([_err("TREE_CYCLE",
                                       f"管段 {e['id']} 形成环，管网不是树",
                                       edge_index=ei)])
            visited[w] = True
            parent[w] = u
            parent_edge[w] = ei
            depth_edges[w] = depth_edges[u] + 1
            height[w] = height[u] + edges[ei]["length"]
            tin[w] = timer
            timer += 1
            order.append(w)
            dfs_stack.append((w, ei, 0))
        else:
            tout[u] = timer - 1
            dfs_stack.pop()

    if sum(visited) != n:
        raise SolveError([_err("TREE_DISCONNECTED",
                               "管网存在互不连通的部分，不能构成单棵树",
                               field="edges")])

    # Binary lifting table for LCA.
    log = max(1, ceil(log2(n)))
    up = [parent[:]]
    for _k in range(1, log + 1):
        prev = up[-1]
        up.append([prev[prev[v]] for v in range(n)])

    def lca(a, b):
        if depth_edges[a] < depth_edges[b]:
            a, b = b, a
        diff = depth_edges[a] - depth_edges[b]
        bit = 0
        while diff:
            if diff & 1:
                a = up[bit][a]
            diff >>= 1
            bit += 1
        if a == b:
            return a
        for k in range(log, -1, -1):
            if up[k][a] != up[k][b]:
                a = up[k][a]
                b = up[k][b]
        return parent[a]

    # Per-edge oriented endpoints: u = root side, v = child.
    edge_uv = [None] * len(edges)
    for ei, e in enumerate(edges):
        a, b = index[e["from"]], index[e["to"]]
        if parent_edge[b] == ei:
            u, v, from_is_u = a, b, True
        else:
            u, v, from_is_u = b, a, False
        edge_uv[ei] = (u, v, from_is_u)

    return {
        "index": index, "root": root, "parent": parent,
        "parent_edge": parent_edge, "height": height,
        "tin": tin, "tout": tout, "order": order,
        "lca": lca, "edge_uv": edge_uv, "adj": adj,
        "depth_edges": depth_edges,
    }


def solve(payload):
    edges, sensors, nodes, n = validate_input(payload)
    tree = build_tree(edges, nodes)
    H = tree["height"]
    tin, tout = tree["tin"], tree["tout"]
    lca = tree["lca"]
    sensor_node = [tree["index"][s["node"]] for s in sensors]
    obs = [s["arrival"] for s in sensors]
    m = len(sensors)

    # Per-edge candidate: constants of the two slope families.
    # plus family (sensor in v-subtree): f = const_p + z
    # minus family (sensor outside)       : f = const_m - z
    candidates = []  # (edge_index, p, q, plus[], minus[], u)
    for ei, e in enumerate(edges):
        u, v, _from_is_u = tree["edge_uv"][ei]
        L = e["length"]
        plus = []   # (sensor_idx, const)
        minus = []  # (sensor_idx, const)
        for si, sn in enumerate(sensor_node):
            if tin[v] <= tin[sn] <= tout[v]:
                const = obs[si] - (H[sn] - H[u])
                plus.append((si, const))
            else:
                w = lca(u, sn)
                c = H[u] + H[sn] - 2 * H[w]  # dist(u, sensor)
                const = obs[si] - c
                minus.append((si, const))

        A = max((c for _, c in plus), default=None)
        C = min((c for _, c in plus), default=None)
        B = max((c for _, c in minus), default=None)
        D = min((c for _, c in minus), default=None)

        def upper(z):
            vals = []
            vals.extend(c + z for _, c in plus)
            vals.extend(c - z for _, c in minus)
            return max(vals)

        def lower(z):
            vals = []
            vals.extend(c + z for _, c in plus)
            vals.extend(c - z for _, c in minus)
            return min(vals)

        if A is None:  # only minus lines -> width constant on whole edge
            p, q = Fraction(0), Fraction(L)
        elif B is None:  # only plus lines
            p, q = Fraction(0), Fraction(L)
        else:
            zu = Fraction(B - A, 2)  # upper envelope slope -1 -> +1
            zl = Fraction(D - C, 2)  # lower envelope slope +1 -> -1
            alpha, beta = sorted((zu, zl))
            p = max(Fraction(0), alpha)
            q = min(Fraction(L), beta)
            if p > q:  # flat minimum lies wholly outside the edge
                if beta < 0:
                    p = q = Fraction(0)
                else:
                    p = q = Fraction(L)

        delta = (upper(p) - lower(p)) / 2  # exact min max-residual on edge
        candidates.append((ei, p, q, plus, minus, u, delta, upper, lower))

    R = min(cand[6] for cand in candidates)
    optimal = [c for c in candidates if c[6] == R]

    solutions = []
    for ei, p, q, plus, minus, u, _delta, upper, lower in optimal:
        e = edges[ei]
        _u, v, from_is_u = tree["edge_uv"][ei]
        L = e["length"]

        # Canonical point: smallest coordinate measured from the input "from"
        # endpoint, then canonical emission time = midpoint of its interval.
        if from_is_u:
            z_can, z_lo, z_hi = p, p, q
        else:
            z_can, z_lo, z_hi = q, q, p  # input coord = L - z
        y_can = Fraction(z_can) if from_is_u else Fraction(L) - z_can
        y_lo = Fraction(z_lo) if from_is_u else Fraction(L) - z_lo
        y_hi = Fraction(z_hi) if from_is_u else Fraction(L) - z_hi
        Uv, Lv = upper(z_can), lower(z_can)
        t_can = (Uv + Lv) / 2

        pos, neg = [], []
        residuals = []
        for si, sn in enumerate(sensor_node):
            in_plus = None
            for idx, c in plus:
                if idx == si:
                    in_plus = (True, c)
                    break
            if in_plus is None:
                for idx, c in minus:
                    if idx == si:
                        in_plus = (False, c)
                        break
            is_plus, c = in_plus
            if is_plus:
                dist = (H[sn] - H[u]) - z_can
                fv = c + z_can
            else:
                # c = obs - dist(u, sensor), so dist(point, sensor) =
                # dist(u, sensor) + z = (obs - c) + z
                dist = Fraction(obs[si] - c) + z_can
                fv = c - z_can
            predicted = t_can + dist
            residual = Fraction(obs[si]) - predicted
            is_pos_witness = (fv == Uv)
            is_neg_witness = (fv == Lv)
            if is_pos_witness:
                pos.append(si)
            if is_neg_witness:
                neg.append(si)
            sign = 0 if residual == 0 else (1 if residual > 0 else -1)
            residuals.append({
                "sensor_id": sensors[si]["id"],
                "node": sensors[si]["node"],
                "observed": obs[si],
                "predicted": frac_json(predicted),
                "residual": frac_json(residual),
                "sign": sign,
                "witness": ("+" if is_pos_witness
                            else "-" if is_neg_witness else ""),
            })

        solutions.append({
            "edge_index": ei,
            "edge_id": e["id"],
            "from_node": e["from"],
            "to_node": e["to"],
            "edge_length": e["length"],
            "coordinate": frac_json(y_can),
            "interval": {"start": frac_json(y_lo), "end": frac_json(y_hi),
                         "degenerate": y_lo == y_hi},
            "time": frac_json(t_can),
            "time_interval_at_coordinate": {
                "start": frac_json(Lv), "end": frac_json(Uv),
            },
            "positive_witnesses": [sensors[si]["id"] for si in pos],
            "negative_witnesses": [sensors[si]["id"] for si in neg],
            "sensor_residuals": residuals,
        })

    solutions.sort(key=lambda s: (s["edge_index"],
                                  Fraction(s["coordinate"]["n"],
                                           s["coordinate"]["d"]),
                                  Fraction(s["time"]["n"],
                                           s["time"]["d"])))

    # Geometric dedup: a node optimal on several incident edges appears once
    # per edge as a degenerate (endpoint) interval. Report each physical
    # point once, keeping the representative with the earliest input edge
    # (non-degenerate intervals are always kept and cover their endpoints).
    covered_nodes: set[str] = set()
    deduped = []
    for s in solutions:
        L = s["edge_length"]
        lo = Fraction(s["interval"]["start"]["n"], s["interval"]["start"]["d"])
        hi = Fraction(s["interval"]["end"]["n"], s["interval"]["end"]["d"])
        end_nodes = []
        if lo == 0:
            end_nodes.append(s["from_node"])
        if hi == L:
            end_nodes.append(s["to_node"])
        if lo == hi and end_nodes:
            node = end_nodes[0]
            if node in covered_nodes:
                continue
            covered_nodes.add(node)
        else:
            covered_nodes.update(end_nodes)
        deduped.append(s)
    solutions = deduped

    return {
        "status": "ok",
        "node_count": n,
        "edge_count": len(edges),
        "sensor_count": len(sensors),
        "optimal_residual": frac_json(R),
        "solution_count": len(solutions),
        "solutions": solutions,
        "tree": {
            "root": nodes[tree["root"]],
            "nodes": [{"id": v, "height": frac_json(Fraction(H[tree["index"][v]]))}
                      for v in nodes],
        },
    }
