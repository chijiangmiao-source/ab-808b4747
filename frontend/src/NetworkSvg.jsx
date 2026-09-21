import { useMemo, useState } from "react";
import { layout } from "./layout";

const fnum = (f) => {
  if (!f) return "";
  if (f.d === 1) return `${f.n}`;
  return `${f.n}/${f.d}`;
};

export default function NetworkSvg({ draft, result, selectedEdge, onSelectEdge }) {
  const [hover, setHover] = useState(null);
  const L = useMemo(
    () => layout(draft.edges.filter((e) => e.from && e.to && Number(e.length) > 0)),
    [draft.edges]
  );

  if (!L) {
    return (
      <div className="svg-empty">
        请至少添加一条管段（填写首端节点、末端节点与正整数长度）。
      </div>
    );
  }
  const { pos, tree, pointOn, width, height } = L;
  const sensorByNode = new Map(
    draft.sensors.filter((s) => s.node).map((s) => [s.node, s])
  );

  // Map result solutions back to edges.
  const solByEdge = new Map();
  if (result) {
    for (const s of result.solutions) {
      const list = solByEdge.get(s.edge_index) ?? [];
      list.push(s);
      solByEdge.set(s.edge_index, list);
    }
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="network-svg" role="img"
         aria-label="管网示意图">
      {/* edges */}
      {draft.edges.map((e, i) => {
        const a = pos.get(e.from);
        const b = pos.get(e.to);
        if (!a || !b) return null;
        const isOpt = solByEdge.has(i);
        const isSel = selectedEdge === i;
        return (
          <g key={`e-${i}`}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  className={`pipe ${isOpt ? "pipe-opt" : ""} ${isSel ? "pipe-sel" : ""}`}
                  onClick={() => onSelectEdge?.(isSel ? null : i)}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)} />
            {/* length label at midpoint */}
            <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 6}
                  className="edge-label" pointerEvents="none">
              {e.id || `#${i + 1}`}={e.length}
            </text>
            {isOpt && (
              <OpticalMarks edge={e} edgeIndex={i} pointOn={pointOn}
                            sols={solByEdge.get(i)} />
            )}
          </g>
        );
      })}

      {/* nodes */}
      {[...pos.entries()].map(([name, p]) => {
        const sensor = sensorByNode.get(name);
        return (
          <g key={`n-${name}`}>
            <circle cx={p.x} cy={p.y} r={sensor ? 7 : 4}
                    className={sensor ? "node-sensor" : "node"} />
            <text x={p.x} y={p.y - 12} className="node-label" pointerEvents="none">
              {name}{sensor ? ` 🎤${sensor.id}` : ""}
            </text>
          </g>
        );
      })}

      {hover !== null && (
        <text x={12} y={height - 12} className="hint">
          管段 {draft.edges[hover].id || `#${hover + 1}`}：
          {draft.edges[hover].from} → {draft.edges[hover].to}
          （点击{selectedEdge === hover ? "取消选中" : "选中"}）
        </text>
      )}
      {(!tree.connected || tree.cyclic) && (
        <text x={12} y={24} className="warn-text">
          {tree.cyclic ? "当前草稿存在环，无法按树布局" : "当前草稿不连通"}
        </text>
      )}
    </svg>
  );
}

function OpticalMarks({ edge, edgeIndex, pointOn, sols }) {
  const marks = [];
  sols.forEach((s, k) => {
    const len = Number(edge.length);
    const startFrac = Number(s.interval.start.n) / Number(s.interval.start.d) / len;
    const endFrac = Number(s.interval.end.n) / Number(s.interval.end.d) / len;
    const p1 = pointOn(edge, Math.max(0, Math.min(1, startFrac)));
    const p2 = pointOn(edge, Math.max(0, Math.min(1, endFrac)));
    const c = pointOn(
      edge,
      (Number(s.coordinate.n) / Number(s.coordinate.d)) / len
    );
    if (p1 && p2) {
      marks.push(
        <line key={`iv-${edgeIndex}-${k}`} x1={p1.x} y1={p1.y}
              x2={p2.x} y2={p2.y} className="opt-interval" />
      );
    }
    if (c) {
      marks.push(
        <circle key={`pt-${edgeIndex}-${k}`} cx={c.x} cy={c.y} r={6}
                className="opt-point">
          <title>{`规范源点：管段 ${s.edge_id}，距 ${edge.from} ${fnum(s.coordinate)}，t=${fnum(s.time)}`}</title>
        </circle>
      );
    }
  });
  return <>{marks}</>;
}
