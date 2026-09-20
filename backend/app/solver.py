"""Exact-rational leak localization on a tree network.

Model
-----
* Pipes are edges (u, v) with positive integer length.  They form a tree.
* Sensor ``i`` sits on node ``n_i`` and reports integer arrival time ``t_i``.
* A source at continuous position emits at unknown time ``t0`` (no prior).
* Arrival prediction:  t0 + tree_distance(source, n_i).

For a point at coordinate ``x`` measured from endpoint ``a`` of edge
``(a, b)`` (length ``L``), the path to a sensor either leaves through ``a``
(distance ``x + d(a, n_i)``, slope +1 in ``x``) or through ``b``
(distance ``(L - x) + d(b, n_i)``, slope -1 in ``x``).  With

    A_i = t_i - constant_i,   residual_i(x, t0) = A_i - slope_i * x - t0

the best ``t0`` for a fixed ``x`` is the midpoint of the residual range and

    g(x) = max_i residual_i - min_i residual_i

is convex piecewise linear on ``[0, L]``.  Its minimum is the edge optimum;
the global optimum is the minimum over edges.  All arithmetic uses
``fractions.Fraction`` so every optimum point / closed interval, emission
time and residual is exact.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

# Graph is represented internally by compact node indices.
Edge = Tuple[int, int, int]  # (u_index, v_index, length)
Sensor = Tuple[int, int]  # (node_index, observed_time)


def _frac_obj(value: Fraction) -> Dict[str, object]:
    """JSON-serialisable exact fraction plus a readable string."""
    num, den = value.numerator, value.denominator
    return {"num": num, "den": den, "text": str(num) if den == 1 else f"{num}/{den}"}


def _root_tree(
    node_count: int,
    edges: Sequence[Edge],
    root: int,
) -> Tuple[List[List[Tuple[int, int, int]]], List[int], List[int]]:
    """Return (adjacency, parent_node, parent_edge_index) rooted at ``root``."""
    adj: List[List[Tuple[int, int, int]]] = [[] for _ in range(node_count)]
    for k, (u, v, length) in enumerate(edges):
        adj[u].append((v, length, k))
        adj[v].append((u, length, k))

    parent = [-1] * node_count
    parent_edge = [-1] * node_count
    parent[root] = root

    stack = [root]
    order: List[int] = []
    while stack:
        node = stack.pop()
        order.append(node)
        for nxt, _length, edge_k in adj[node]:
            if nxt == parent[node]:
                continue
            parent[nxt] = node
            parent_edge[nxt] = edge_k
            stack.append(nxt)
    return adj, parent, parent_edge


def _subtree_intervals(
    node_count: int,
    adj: Sequence[Sequence[Tuple[int, int, int]]],
    root: int,
) -> Tuple[List[int], List[int]]:
    """Iterative DFS pre-order timer / subtree exit timer."""
    tin = [-1] * node_count
    tout = [-1] * node_count
    timer = 0
    # (node, parent, entered)
    stack: List[Tuple[int, int, bool]] = [(root, -1, False)]
    while stack:
        node, par, entered = stack.pop()
        if entered:
            tout[node] = timer - 1
            continue
        tin[node] = timer
        timer += 1
        stack.append((node, par, True))
        for nxt, _length, _edge_k in reversed(adj[node]):
            if nxt != par:
                stack.append((nxt, node, False))
    return tin, tout


def _distances_from(
    node_count: int,
    adj: Sequence[Sequence[Tuple[int, int, int]]],
    source: int,
) -> List[int]:
    """Exact integer distances from ``source`` to every node (tree DFS)."""
    dist = [-1] * node_count
    dist[source] = 0
    stack = [source]
    while stack:
        node = stack.pop()
        for nxt, length, _edge_k in adj[node]:
            if dist[nxt] == -1:
                dist[nxt] = dist[node] + length
                stack.append(nxt)
    return dist


def _edge_minimum(
    length: int,
    p_max: Optional[int],
    p_min: Optional[int],
    m_max: Optional[int],
    m_min: Optional[int],
) -> Tuple[Fraction, List[Tuple[Fraction, Fraction, List[Tuple[Fraction, Fraction]]]]]:
    """Minimise g(x) on one edge.

    P-lines (sensor reached through the parent endpoint, slope +1 in the
    distance, hence residual line slope -1):  residual = A - x.
    M-lines (sensor reached through the child endpoint): residual = A + x.

    ``upper(x) = max`` of active lines, ``lower(x) = min`` of active lines,
    ``g = upper - lower``.  Returns (g*, [(x_lo, x_hto, t0_pieces)]) where a
    t0 piece is (x_from, x_to, t0_from, t0_to).
    """
    upper: List[Tuple[int, int]] = []
    lower: List[Tuple[int, int]] = []
    if p_max is not None:
        upper.append((-1, p_max))
        lower.append((-1, p_min))
    if m_max is not None:
        upper.append((1, m_max))
        lower.append((1, m_min))

    L = Fraction(length)

    def value(lines: Sequence[Tuple[int, int]], x: Fraction) -> Fraction:
        result = None
        for slope, intercept in lines:
            cand = intercept + slope * x
            if result is None or cand > result:
                result = cand
        return result  # type: ignore[return-value]

    def upper_at(x: Fraction) -> Fraction:
        return value(upper, x)

    def lower_at(x: Fraction) -> Fraction:
        result = None
        for slope, intercept in lower:
            cand = intercept + slope * x
            if result is None or cand < result:
                result = cand
        return result  # type: ignore[return-value]

    # Kinks: intersection of the -1 line and the +1 line, if both exist.
    kinks: List[Fraction] = []
    if len(upper) == 2:
        (s1, c1), (s2, c2) = upper
        kinks.append(Fraction(c1 - c2, s2 - s1))  # (a - b) / 2
    if len(lower) == 2:
        (s1, c1), (s2, c2) = lower
        kinks.append(Fraction(c1 - c2, s2 - s1))

    points = {Fraction(0), L}
    for kink in kinks:
        if 0 < kink < L:
            points.add(kink)
    ordered = sorted(points)

    g_values = [upper_at(x) - lower_at(x) for x in ordered]
    g_star = min(g_values)

    intervals: List[Tuple[Fraction, Fraction, List[Tuple[Fraction, Fraction]]]] = []
    i = 0
    while i < len(ordered):
        if g_values[i] != g_star:
            i += 1
            continue
        j = i
        while j + 1 < len(ordered) and g_values[j + 1] == g_star:
            j += 1
        x_lo, x_hi = ordered[i], ordered[j]

        # t0(x) = (upper(x) + lower(x)) / 2 is piecewise linear; split at any
        # interior kink so the returned emission-time pieces stay linear.
        breaks = [x_lo]
        for kink in kinks:
            if x_lo < kink < x_hi:
                breaks.append(kink)
        breaks.append(x_hi)
        pieces: List[Tuple[Fraction, Fraction]] = []
        for bp, bq in zip(breaks, breaks[1:]):
            t0_p = (upper_at(bp) + lower_at(bp)) / 2
            t0_q = (upper_at(bq) + lower_at(bq)) / 2
            pieces.append((bp, bq, t0_p, t0_q))  # type: ignore[arg-type]
        intervals.append((x_lo, x_hi, pieces))  # type: ignore[arg-type]
        i = j + 1

    return g_star, intervals


def solve(
    node_ids: Sequence[int],
    edges: Sequence[Edge],
    sensors: Sequence[Sensor],
) -> Dict[str, object]:
    """Compute the L-infinity optimum over the whole tree.

    ``edges`` keeps the user-supplied order and orientation
    ``(u_index, v_index, length)``; coordinates in the result are measured
    from that first-listed ("head") endpoint.
    """
    n = len(node_ids)
    root = sensors[0][0]
    adj, parent, parent_edge = _root_tree(n, edges, root)
    tin, tout = _subtree_intervals(n, adj, root)

    sensor_nodes = [node for node, _time in sensors]
    sensor_times = [time for _node, time in sensors]
    sensor_dist = [_distances_from(n, adj, node) for node in sensor_nodes]

    best: Optional[Fraction] = None
    per_edge: List[Tuple[Fraction, List[Tuple[Fraction, Fraction, list]]]] = []

    for k, (u, v, length) in enumerate(edges):
        child = v if parent_edge[v] == k else u
        head = u if child == v else v
        # distance to child node = parent distance + length, but use sensor
        # distance matrices directly:
        p_max = p_min = None
        m_max = m_min = None
        for i, (snode, stime) in enumerate(zip(sensor_nodes, sensor_times)):
            inside = tin[child] <= tin[snode] <= tout[child]
            if inside:
                # path via child: distance = (L - x) + d(child, sensor)
                a_value = stime - (length + sensor_dist[i][child])
                m_max = a_value if m_max is None or a_value > m_max else m_max
                m_min = a_value if m_min is None or a_value < m_min else m_min
            else:
                # path via parent-side head: distance = x + d(head, sensor)
                a_value = stime - sensor_dist[i][head]
                p_max = a_value if p_max is None or a_value > p_max else p_max
                p_min = a_value if p_min is None or a_value < p_min else p_min

        g_star, intervals = _edge_minimum(length, p_max, p_min, m_max, m_min)
        per_edge.append((g_star, intervals))
        if best is None or g_star < best:
            best = g_star

    assert best is not None
    # With t0 free, max absolute residual at the optimal midpoint t0 is half
    # the residual span g*; minimizer set is unchanged.
    best_half = best / 2

    # Canonical solution: earliest edge in input order attaining g*, smallest
    # coordinate measured from the user-supplied head endpoint.
    canonical_edge = next(k for k, (g_star, _iv) in enumerate(per_edge) if g_star == best)
    u, v, length = edges[canonical_edge]
    child = v if parent_edge[v] == canonical_edge else u
    head = u if child == v else v
    internal_lo = per_edge[canonical_edge][1][0][0]
    x_canon_internal = internal_lo
    x_canon = x_canon_internal if head == u else Fraction(length) - x_canon_internal

    # Residuals at the canonical point (computed in internal orientation).
    a_node, b_node = head, child
    p_lines: Dict[int, int] = {}
    m_lines: Dict[int, int] = {}
    for i, (snode, stime) in enumerate(zip(sensor_nodes, sensor_times)):
        inside = tin[b_node] <= tin[snode] <= tout[b_node]
        if inside:
            m_lines[i] = stime - (length + sensor_dist[i][b_node])
        else:
            p_lines[i] = stime - sensor_dist[i][a_node]

    residuals_raw: List[Fraction] = []
    for i in range(len(sensors)):
        if i in p_lines:
            residuals_raw.append(Fraction(p_lines[i]) - x_canon_internal)
        else:
            residuals_raw.append(Fraction(m_lines[i]) + x_canon_internal)
    t0_canon = (max(residuals_raw) + min(residuals_raw)) / 2

    residual_rows: List[Dict[str, object]] = []
    positive_witnesses: List[int] = []
    negative_witnesses: List[int] = []
    for i, (snode, stime) in enumerate(zip(sensor_nodes, sensor_times)):
        if i in p_lines:
            distance = sensor_dist[i][a_node] + x_canon_internal
        else:
            distance = length + sensor_dist[i][b_node] - x_canon_internal
        predicted = t0_canon + distance
        residual = Fraction(stime) - predicted
        residuals_raw_check = residual
        assert residuals_raw_check == residuals_raw[i] - t0_canon
        role = None
        if residual == best_half:
            role = "positive"
            positive_witnesses.append(i)
        elif residual == -best_half:
            role = "negative"
            negative_witnesses.append(i)
        residual_rows.append(
            {
                "sensor_index": i,
                "node": node_ids[snode],
                "observed": stime,
                "distance": _frac_obj(distance),
                "predicted": _frac_obj(predicted),
                "residual": _frac_obj(residual),
                "abs_residual": _frac_obj(abs(residual)),
                "extremal": role,
            }
        )

    # All co-optimal intervals, converted to user orientation (head = u).
    optima: List[Dict[str, object]] = []
    for k, (g_star, intervals) in enumerate(per_edge):
        if g_star != best:
            continue
        eu, ev, elen = edges[k]
        echild = ev if parent_edge[ev] == k else eu
        ehead = eu if echild == ev else ev
        for lo, hi, pieces in intervals:
            if ehead == eu:
                start, end = lo, hi
                mapped_pieces = [
                    {
                        "x_start": _frac_obj(xp),
                        "x_end": _frac_obj(xq),
                        "t0_start": _frac_obj(tp),
                        "t0_end": _frac_obj(tq),
                    }
                    for xp, xq, tp, tq in pieces
                ]
            else:
                start, end = Fraction(elen) - hi, Fraction(elen) - lo
                mapped_pieces = [
                    {
                        "x_start": _frac_obj(Fraction(elen) - xq),
                        "x_end": _frac_obj(Fraction(elen) - xp),
                        "t0_start": _frac_obj(tq),
                        "t0_end": _frac_obj(tp),
                    }
                    for xp, xq, tp, tq in reversed(pieces)
                ]
            optima.append(
                {
                    "edge_index": k,
                    "from_node": node_ids[eu],
                    "to_node": node_ids[ev],
                    "length": elen,
                    "coordinate_start": _frac_obj(start),
                    "coordinate_end": _frac_obj(end),
                    "point": start == end,
                    "t0_segments": mapped_pieces,
                }
            )

    return {
        "optimal_value": _frac_obj(best_half),
        "canonical": {
            "edge_index": canonical_edge,
            "from_node": node_ids[u],
            "to_node": node_ids[v],
            "length": length,
            "coordinate": _frac_obj(x_canon),
            "emission_time": _frac_obj(t0_canon),
        },
        "optima": optima,
        "residuals": residual_rows,
        "witnesses": {
            "positive": positive_witnesses,
            "negative": negative_witnesses,
        },
        "node_count": n,
        "edge_count": len(edges),
        "sensor_count": len(sensors),
    }
