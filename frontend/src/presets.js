// Preset networks loaded into the editor. Times are integer arrivals in the
// same unit as pipe lengths (wave speed normalised to 1).
export const PRESETS = {
  star: {
    label: '示例 · 星形管网（含误差）',
    draft: {
      nodes: [1, 2, 3, 4, 5],
      edges: [
        { u: 1, v: 2, length: 10 },
        { u: 1, v: 3, length: 6 },
        { u: 1, v: 4, length: 8 },
        { u: 1, v: 5, length: 12 },
      ],
      sensors: [
        { node: 2, time: 21 },
        { node: 3, time: 16 },
        { node: 4, time: 18 },
        { node: 5, time: 23 },
      ],
    },
  },
  path: {
    label: '示例 · 直线路径（精确解）',
    draft: {
      nodes: [10, 20, 30, 40],
      edges: [
        { u: 10, v: 20, length: 4 },
        { u: 20, v: 30, length: 6 },
        { u: 30, v: 40, length: 10 },
      ],
      // source x=3 on edge 20-30, t0=7 -> arrivals 14, 10, 20
      sensors: [
        { node: 10, time: 14 },
        { node: 20, time: 10 },
        { node: 40, time: 20 },
      ],
    },
  },
  interval: {
    label: '示例 · 无传感器支管整段同优',
    draft: {
      nodes: [1, 2, 3, 4],
      edges: [
        { u: 1, v: 2, length: 10 },
        { u: 1, v: 3, length: 10 },
        { u: 1, v: 4, length: 10 },
      ],
      sensors: [
        { node: 2, time: 15 },
        { node: 3, time: 15 },
      ],
    },
  },
}

export function makeEmptyDraft() {
  return {
    nodes: [{ id: 1 }, { id: 2 }, { id: 3 }].map((n) => String(n.id)),
    edges: [{ u: '1', v: '2', length: '5' }],
    sensors: [
      { node: '2', time: '' },
      { node: '3', time: '' },
    ],
  }
}
