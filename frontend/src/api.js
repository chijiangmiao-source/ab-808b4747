const BASE = '/api'

export async function health() {
  const resp = await fetch(`${BASE}/health`)
  if (!resp.ok) throw new Error(`health ${resp.status}`)
  return resp.json()
}

export async function localize(payload) {
  const resp = await fetch(`${BASE}/localize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  let data = null
  try {
    data = await resp.json()
  } catch {
    throw new Error(`服务器返回了无法解析的内容（HTTP ${resp.status}）`)
  }
  if (!resp.ok || data.ok === false) {
    const err = new Error('定位请求被拒绝')
    err.errors = data.errors || [
      { kind: 'network', index: null, field: null, message: `HTTP ${resp.status}` },
    ]
    throw err
  }
  return data.result
}
