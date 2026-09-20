// Deterministic layered layout for a tree given as [{u,v,length}, ...]
// over a set of node ids. Returns a Map id -> {x, y, depth}.
//
// The highest-degree node becomes the root; a post-order walk assigns one
// horizontal slot per leaf and centres each subtree over its children.
export function layoutTree(nodes, edges) {
  const adj = new Map()
  for (const id of nodes) adj.set(id, [])
  for (const [k, e] of edges.entries()) {
    if (!adj.has(e.u) || !adj.has(e.v)) continue
    adj.get(e.u).push({ to: e.v, edgeIndex: k })
    adj.get(e.v).push({ to: e.u, edgeIndex: k })
  }

  let root = nodes[0]
  let bestDegree = -1
  for (const id of nodes) {
    const d = adj.get(id)?.length ?? 0
    if (d > bestDegree || (d === bestDegree && id < root)) {
      bestDegree = d
      root = id
    }
  }

  const parent = new Map()
  const parentEdge = new Map()
  const childrenOf = new Map(nodes.map((id) => [id, []]))
  const order = []
  const stack = [root]
  parent.set(root, null)
  while (stack.length) {
    const cur = stack.pop()
    order.push(cur)
    for (const { to, edgeIndex } of adj.get(cur) || []) {
      if (to === parent.get(cur)) continue
      if (parent.has(to)) continue
      parent.set(to, cur)
      parentEdge.set(to, edgeIndex)
      childrenOf.get(cur).push(to)
      stack.push(to)
    }
  }
  // Stable child order: by node id.
  for (const list of childrenOf.values()) list.sort((a, b) => a - b)

  const H_GAP = 26
  const V_GAP = 78
  const pos = new Map()
  let slot = 0
  for (let i = order.length - 1; i >= 0; i--) {
    const id = order[i]
    const kids = childrenOf.get(id)
    if (kids.length === 0) {
      pos.set(id, { x: slot * H_GAP, depth: 0 })
      slot += 1
    } else {
      let sum = 0
      let maxDepth = 0
      for (const k of kids) {
        sum += pos.get(k).x
        maxDepth = Math.max(maxDepth, pos.get(k).depth)
      }
      pos.set(id, { x: sum / kids.length, depth: maxDepth + 1 })
    }
  }

  const result = new Map()
  const X0 = pos.get(root).x
  for (const id of order) {
    result.set(id, { x: pos.get(id).x - X0, y: pos.get(id).depth * V_GAP })
  }
  // Normalise x so minimum is 0.
  let minX = Infinity
  for (const p of result.values()) minX = Math.min(minX, p.x)
  for (const p of result.values()) p.x -= minX
  return { positions: result, root, childrenOf, parent, parentEdge }
}

export function pointOnEdge(posU, posV, length, xFromU) {
  const t = length === 0 ? 0 : Number(xFromU) / Number(length)
  return {
    x: posU.x + (posV.x - posU.x) * t,
    y: posU.y + (posV.y - posU.y) * t,
  }
}

export function fracNumber(f) {
  return Number(f.num) / Number(f.den)
}
