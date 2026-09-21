// Deterministic top-down layout for a tree of pipe segments.
// y is proportional to cumulative pipe length from the root;
// x is the mean of child x coordinates (leaves spaced evenly).

export function buildTree(edges) {
  const adj = new Map();
  const nodes = new Set();
  for (const e of edges) {
    if (!e.from || !e.to) continue;
    nodes.add(e.from);
    nodes.add(e.to);
    if (!adj.has(e.from)) adj.set(e.from, []);
    if (!adj.has(e.to)) adj.set(e.to, []);
    adj.get(e.from).push({ node: e.to, edge: e });
    adj.get(e.to).push({ node: e.from, edge: e });
  }
  if (nodes.size === 0 || edges.length === 0) return null;

  const root = edges[0].from;
  const parent = new Map([[root, null]]);
  const parentEdge = new Map([[root, null]]);
  const children = new Map();
  const order = [];
  const stack = [root];
  let cyclic = false;
  while (stack.length) {
    const u = stack.pop();
    order.push(u);
    const kids = [];
    for (const { node: v, edge } of adj.get(u) ?? []) {
      if (v === parent.get(u)) continue;
      if (parent.has(v)) {
        cyclic = true;
        continue;
      }
      parent.set(v, u);
      parentEdge.set(v, edge);
      kids.push(v);
      stack.push(v);
    }
    children.set(u, kids);
  }
  const connected = parent.size === nodes.size;
  return { adj, nodes: [...nodes], root, parent, parentEdge,
           children, order, cyclic, connected };
}

export function layout(edges, width = 1000, height = 560) {
  const tree = buildTree(edges);
  if (!tree) return null;
  const { root, children, parent, parentEdge, order } = tree;

  // postorder traversal for x (leaf fan-in)
  const post = [];
  (function dfs(u) {
    for (const v of children.get(u)) dfs(v);
    post.push(u);
  })(root);

  let leafCounter = 0;
  const x0 = new Map();
  for (const u of post) {
    const kids = children.get(u);
    if (kids.length === 0) {
      x0.set(u, leafCounter++);
    } else {
      x0.set(u, kids.reduce((s, v) => s + x0.get(v), 0) / kids.length);
    }
  }

  // y: cumulative pipe length from root; order is parent-before-child.
  const y0 = new Map([[root, 0]]);
  for (const u of order) {
    if (u === root) continue;
    y0.set(u, y0.get(parent.get(u)) + Number(parentEdge.get(u).length || 0));
  }

  const maxDepth = Math.max(...[...y0.values()], 1);
  const span = Math.max(leafCounter - 1, 1);
  const mx = 70, my = 60;
  const pos = new Map();
  for (const n of x0.keys()) {
    pos.set(n, {
      x: mx + (x0.get(n) / span) * (width - 2 * mx),
      y: my + (y0.get(n) / maxDepth) * (height - 2 * my),
    });
  }

  // point at coordinate z measured from the input "from" endpoint
  const pointOn = (edge, frac) => {
    const a = pos.get(edge.from);
    const b = pos.get(edge.to);
    if (!a || !b) return null;
    return { x: a.x + frac * (b.x - a.x), y: a.y + frac * (b.y - a.y) };
  };

  return { tree, pos, width, height, pointOn };
}
