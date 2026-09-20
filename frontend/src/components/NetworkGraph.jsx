import React from 'react'
import { layoutTree, pointOnEdge, fracNumber } from '../layout'

const PADDING = 46
const SCALE_W = 640 // nominal width before fitting

function asInt(raw) {
  if (raw === null || raw === undefined) return null
  const text = String(raw).trim()
  if (text === '' || !/^[+-]?\d+$/.test(text)) return null
  const n = Number(text)
  return Number.isSafeInteger(n) ? n : null
}

export default function NetworkGraph({ draft, result, highlightSensors }) {
  const parsed = React.useMemo(() => {
    const nodes = []
    for (const raw of draft.nodes) {
      const v = asInt(typeof raw === 'object' ? raw.id : raw)
      if (v !== null) nodes.push(v)
    }
    const edges = draft.edges
      .map((e, i) => ({ u: asInt(e.u), v: asInt(e.v), length: asInt(e.length), _i: i }))
      .filter((e) => e.u !== null && e.v !== null && e.length !== null && e.length > 0)
    // keep only edges referencing known nodes for the drawing
    const nodeSet = new Set(nodes)
    const okEdges = edges.filter((e) => nodeSet.has(e.u) && nodeSet.has(e.v))
    return { nodes, edges: okEdges }
  }, [draft])

  const layout = React.useMemo(() => {
    if (parsed.nodes.length < 1 || parsed.edges.length < 1) return null
    try {
      const ids = [...new Set([...parsed.nodes, ...parsed.edges.flatMap((e) => [e.u, e.v])])]
      return layoutTree(ids, parsed.edges)
    } catch {
      return null
    }
  }, [parsed])

  if (!layout) {
    return <div className="graph-empty">输入至少一条引用有效节点的管段后，这里会显示树状管网。</div>
  }

  const { positions } = layout
  const xs = [...positions.values()].map((p) => p.x)
  const ys = [...positions.values()].map((p) => p.y)
  const minX = Math.min(...xs, 0)
  const maxX = Math.max(...xs, 0)
  const minY = Math.min(...ys, 0)
  const maxY = Math.max(...ys, 0)
  const width = maxX - minX + PADDING * 2
  const height = maxY - minY + PADDING * 2
  const fit = Math.min(1, SCALE_W / width)
  const tx = (p) => (p.x - minX + PADDING) * fit
  const ty = (p) => (p.y - minY + PADDING) * fit

  const sensorByNode = new Map()
  draft.sensors.forEach((s, i) => {
    const n = Number(s.node)
    if (Number.isInteger(n)) sensorByNode.set(n, i)
  })
  const hlNodes = new Set()
  for (const i of highlightSensors || []) {
    const raw = draft.sensors[i]?.node
    if (raw !== undefined && Number.isInteger(Number(raw))) hlNodes.add(Number(raw))
  }

  const optEdges = new Set((result?.optima || []).map((o) => o.edge_index))
  const canonical = result?.canonical

  return (
    <svg viewBox={`0 0 ${width * fit} ${height * fit}`} className="network-svg" role="img" aria-label="树状管网图">
      {/* pipes */}
      {parsed.edges.map((e) => {
        const a = positions.get(Number(e.u))
        const b = positions.get(Number(e.v))
        if (!a || !b) return null
        const optimal = optEdges.has(e._i)
        const midX = (tx(a) + tx(b)) / 2
        const midY = (ty(a) + ty(b)) / 2
        return (
          <g key={e._i}>
            <line x1={tx(a)} y1={ty(a)} x2={tx(b)} y2={ty(b)}
              className={optimal ? 'pipe pipe-optimal' : 'pipe'} />
            <text x={midX} y={midY - 4} className="edge-label" textAnchor="middle">
              #{e._i} · {e.length}
            </text>
          </g>
        )
      })}

      {/* all co-optimal intervals / points */}
      {result?.optima?.map((opt, oi) => {
        const edge = draft.edges[opt.edge_index]
        const a = positions.get(Number(edge.u))
        const b = positions.get(Number(edge.v))
        if (!a || !b) return null
        const L = Number(opt.length)
        const p0 = pointOnEdge(a, b, L, fracNumber(opt.coordinate_start))
        const p1 = pointOnEdge(a, b, L, fracNumber(opt.coordinate_end))
        const q0 = { x: tx(p0), y: ty(p0) }
        const q1 = { x: tx(p1), y: ty(p1) }
        const isCanonical = canonical && canonical.edge_index === opt.edge_index
        if (opt.point) {
          return (
            <circle key={`o${oi}`} cx={q0.x} cy={q0.y}
              r={isCanonical ? 8 : 5}
              className={isCanonical ? 'opt-point-canonical' : 'opt-point'} />
          )
        }
        return (
          <line key={`o${oi}`} x1={q0.x} y1={q0.y} x2={q1.x} y2={q1.y}
            className={isCanonical ? 'opt-interval-canonical' : 'opt-interval'} />
        )
      })}

      {/* nodes */}
      {[...positions.entries()].map(([id, p]) => {
        const sensorIdx = sensorByNode.get(id)
        const isSensor = sensorIdx !== undefined
        const lit = hlNodes.has(id)
        return (
          <g key={id} transform={`translate(${tx(p)},${ty(p)})`} className={lit ? 'sensor-lit' : ''}>
            <circle r={isSensor ? 7 : 5} className={isSensor ? 'node node-sensor' : 'node'} />
            <text y={-12} className="node-label" textAnchor="middle">{id}</text>
            {isSensor && <text y={4} className="sensor-glyph" textAnchor="middle">{sensorIdx}</text>}
          </g>
        )
      })}

      {/* canonical source marker on top */}
      {canonical && (() => {
        const edge = draft.edges[canonical.edge_index]
        const a = positions.get(Number(edge.u))
        const b = positions.get(Number(edge.v))
        if (!a || !b) return null
        const p = pointOnEdge(a, b, Number(canonical.length), fracNumber(canonical.coordinate))
        return (
          <g transform={`translate(${tx(p)},${ty(p)})`}>
            <circle r={11} className="source-halo" />
            <path d="M0,-6 L6,6 L-6,6 Z" className="source-marker" />
          </g>
        )
      })()}
    </svg>
  )
}
