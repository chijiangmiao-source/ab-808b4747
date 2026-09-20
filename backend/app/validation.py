"""Input validation with exact error locations.

The editor keeps raw drafts (numbers may still be text), so every field is
parsed from ``int``-or-string and failures are reported against the exact
row index and field instead of as a generic schema error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

NODE_MIN, NODE_MAX = 2, 2000
SENSOR_MIN, SENSOR_MAX = 2, 128
ID_BOUND = 1_000_000_000
LENGTH_MIN, LENGTH_BOUND = 1, 1_000_000_000
TIME_BOUND = 1_000_000_000


@dataclass
class Issue(Exception):
    kind: str  # "network" | "node" | "edge" | "sensor"
    index: Optional[int]
    field: Optional[str]
    message: str

    def as_dict(self) -> Dict[str, Optional[object]]:
        return {"kind": self.kind, "index": self.index, "field": self.field, "message": self.message}


class DraftValidationError(Exception):
    def __init__(self, issues: List[Issue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def _parse_int(raw: Any) -> Optional[int]:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if raw.is_integer():
            return int(raw)
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if text and (text[0] in "+-"):
            body = text[1:]
        else:
            body = text
        if body.isdigit():
            return int(text)
    return None


def _require_int(kind: str, index: int, field: str, raw: Any) -> int:
    value = _parse_int(raw)
    if value is None:
        raise DraftValidationError(
            [Issue(kind, index, field, f"{field} 必须是整数，当前为 {raw!r}")]
        )
    return value


def validate_and_build(payload: Dict[str, Any]) -> Tuple[List[int], List[Tuple[int, int, int, int]], List[Tuple[int, int, int]]]:
    """Return (node_ids, edges (u, v, length, input_index), sensors (node, time, input_index))."""
    issues: List[Issue] = []

    raw_nodes = payload.get("nodes")
    raw_edges = payload.get("edges")
    raw_sensors = payload.get("sensors")

    if not isinstance(raw_nodes, list):
        raise DraftValidationError([Issue("network", None, "nodes", "缺少节点列表 nodes")])
    if not isinstance(raw_edges, list):
        raise DraftValidationError([Issue("network", None, "edges", "缺少管段列表 edges")])
    if not isinstance(raw_sensors, list):
        raise DraftValidationError([Issue("network", None, "sensors", "缺少传感器列表 sensors")])

    if not (NODE_MIN <= len(raw_nodes) <= NODE_MAX):
        issues.append(
            Issue("network", None, "nodes", f"节点数必须在 {NODE_MIN} 到 {NODE_MAX} 之间，当前 {len(raw_nodes)}")
        )
    if not (SENSOR_MIN <= len(raw_sensors) <= SENSOR_MAX):
        issues.append(
            Issue("network", None, "sensors", f"传感器数量必须在 {SENSOR_MIN} 到 {SENSOR_MAX} 之间，当前 {len(raw_sensors)}")
        )
    if len(raw_edges) > NODE_MAX - 1:
        issues.append(Issue("network", None, "edges", f"管段数量超过树的上限 {NODE_MAX - 1}"))

    # Nodes.
    node_ids: List[int] = []
    seen_ids: Dict[int, int] = {}
    for i, raw in enumerate(raw_nodes):
        value = _parse_int(raw)
        if value is None:
            issues.append(Issue("node", i, "id", f"节点编号必须是整数，当前为 {raw!r}"))
            continue
        if not (-ID_BOUND <= value <= ID_BOUND):
            issues.append(Issue("node", i, "id", f"节点编号 {value} 越界（|id| ≤ {ID_BOUND}）"))
            continue
        if value in seen_ids:
            issues.append(Issue("node", i, "id", f"节点编号 {value} 与第 {seen_ids[value]} 行重复"))
            continue
        seen_ids[value] = i
        node_ids.append(value)

    id_set = set(seen_ids)

    # Edges.
    edges: List[Tuple[int, int, int, int]] = []
    seen_undirected: Dict[Tuple[int, int], int] = {}
    for i, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            issues.append(Issue("edge", i, None, "管段行格式错误"))
            continue
        u = _parse_int(raw.get("u"))
        v = _parse_int(raw.get("v"))
        length = _parse_int(raw.get("length"))
        row_ok = True
        if u is None:
            issues.append(Issue("edge", i, "u", f"首端节点必须是整数，当前为 {raw.get('u')!r}"))
            row_ok = False
        if v is None:
            issues.append(Issue("edge", i, "v", f"末端节点必须是整数，当前为 {raw.get('v')!r}"))
            row_ok = False
        if u is not None and v is not None and u == v:
            issues.append(Issue("edge", i, "v", "管段两端必须是不同节点（不允许自环）"))
            row_ok = False
        if length is None:
            issues.append(Issue("edge", i, "length", f"管段长度必须是整数，当前为 {raw.get('length')!r}"))
            row_ok = False
        elif not (LENGTH_MIN <= length <= LENGTH_BOUND):
            issues.append(
                Issue("edge", i, "length", f"管段长度必须为 {LENGTH_MIN} 到 {LENGTH_BOUND} 的正整数，当前 {length}")
            )
            row_ok = False
        if u is not None and u not in id_set:
            issues.append(Issue("edge", i, "u", f"引用的节点 {u} 不存在"))
            row_ok = False
        if v is not None and v not in id_set:
            issues.append(Issue("edge", i, "v", f"引用的节点 {v} 不存在"))
            row_ok = False
        if row_ok:
            key = (min(u, v), max(u, v))  # type: ignore[arg-type]
            if key in seen_undirected:
                issues.append(Issue("edge", i, None, f"与第 {seen_undirected[key]} 行管段重复（平行边）"))
                continue
            seen_undirected[key] = i
            edges.append((u, v, length, i))  # type: ignore[arg-type]

    # Sensors.
    sensors: List[Tuple[int, int, int]] = []
    seen_sensor_node: Dict[int, int] = {}
    for i, raw in enumerate(raw_sensors):
        if not isinstance(raw, dict):
            issues.append(Issue("sensor", i, None, "传感器行格式错误"))
            continue
        node = _parse_int(raw.get("node"))
        time_value = _parse_int(raw.get("time"))
        row_ok = True
        if node is None:
            issues.append(Issue("sensor", i, "node", f"所在节点必须是整数，当前为 {raw.get('node')!r}"))
            row_ok = False
        elif node not in id_set:
            issues.append(Issue("sensor", i, "node", f"引用的节点 {node} 不存在"))
            row_ok = False
        elif node in seen_sensor_node:
            issues.append(
                Issue("sensor", i, "node", f"节点 {node} 上已有传感器（第 {seen_sensor_node[node]} 行），传感器须位于不同节点")
            )
            row_ok = False
        if time_value is None:
            issues.append(Issue("sensor", i, "time", f"到达时刻必须是整数，当前为 {raw.get('time')!r}"))
            row_ok = False
        elif not (-TIME_BOUND <= time_value <= TIME_BOUND):
            issues.append(Issue("sensor", i, "time", f"到达时刻 {time_value} 越界（|t| ≤ {TIME_BOUND}）"))
            row_ok = False
        if row_ok:
            seen_sensor_node[node] = i  # type: ignore[index]
            sensors.append((node, time_value, i))  # type: ignore[arg-type]

    if issues:
        # Structural tree checks only make sense when every node/edge row was
        # parsed successfully, but sensor errors must not suppress them.
        structural_ok = not any(e.kind in ("node", "edge") for e in issues)
        if not structural_ok:
            raise DraftValidationError(issues)
    else:
        structural_ok = True

    # Tree check: on the unique-node set, must have exactly n-1 edges and be connected.
    n = len(node_ids)
    if len(edges) != n - 1:
        issues.append(
            Issue("network", None, "edges", f"树必须恰好包含 n-1 = {n - 1} 条管段，当前 {len(edges)} 条（无法成树）")
        )
    else:
        index_of = {node_id: i for i, node_id in enumerate(node_ids)}
        adj: List[List[int]] = [[] for _ in range(n)]
        for u, v, _length, _idx in edges:
            a, b = index_of[u], index_of[v]
            adj[a].append(b)
            adj[b].append(a)

        seen = [False] * n
        stack = [0]
        seen[0] = True
        reached = 0
        while stack:
            cur = stack.pop()
            reached += 1
            for nxt in adj[cur]:
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
        if reached != n:
            issues.append(
                Issue("network", None, "edges", f"管段未连通全部 {n} 个节点（仅连通 {reached} 个），无法构成树")
            )

    if issues:
        raise DraftValidationError(issues)

    return node_ids, edges, sensors
