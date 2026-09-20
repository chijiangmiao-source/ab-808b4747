import React from 'react'
import { health, localize } from './api'
import { PRESETS } from './presets'
import NetworkEditor from './components/NetworkEditor.jsx'
import NetworkGraph from './components/NetworkGraph.jsx'
import ResultPanel from './components/ResultPanel.jsx'

const STORAGE_KEY = 'leak-audit-draft-v1'

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* fall through */ }
  return structuredClone(PRESETS.star.draft)
}

export default function App() {
  const [draft, setDraft] = React.useState(loadDraft)
  const [result, setResult] = React.useState(null)
  const [errors, setErrors] = React.useState([])
  const [busy, setBusy] = React.useState(false)
  const [apiState, setApiState] = React.useState('checking')
  const [highlight, setHighlight] = React.useState([])

  React.useEffect(() => {
    let alive = true
    health()
      .then(() => alive && setApiState('up'))
      .catch(() => alive && setApiState('down'))
    const timer = setInterval(() => {
      health()
        .then(() => alive && setApiState((s) => (s === 'down' ? 'up' : s)))
        .catch(() => alive && setApiState('down'))
    }, 10000)
    return () => { alive = false; clearInterval(timer) }
  }, [])

  React.useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(draft)) } catch { /* ignore */ }
  }, [draft])

  const submit = async () => {
    setBusy(true)
    setErrors([])
    // NOTE: the draft is deliberately left untouched on failure so the user
    // can fix the located field without losing any row.
    try {
      const r = await localize(structuredClone(draft))
      setResult(r)
      setErrors([])
    } catch (e) {
      setResult(null)
      setErrors(e.errors || [{ kind: 'network', index: null, field: null, message: e.message }])
    } finally {
      setBusy(false)
    }
  }

  const loadPreset = (key) => {
    setDraft(structuredClone(PRESETS[key].draft))
    setResult(null)
    setErrors([])
  }

  const clearResult = () => { setResult(null); setErrors([]) }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>树状管网声学泄漏定位审计台</h1>
          <p className="subtitle">
            精确有理数 L∞ 定位 · 未知发声时刻无先验 · 解为连续位置上的点或闭区间
          </p>
        </div>
        <div className={`health health-${apiState}`}>
          <span className="health-dot" />
          API {apiState === 'up' ? '已连通' : apiState === 'checking' ? '探测中…' : '不可用'}
        </div>
      </header>

      <div className="toolbar">
        <span className="toolbar-label">载入草稿：</span>
        {Object.entries(PRESETS).map(([key, p]) => (
          <button key={key} className="btn" onClick={() => loadPreset(key)}>{p.label}</button>
        ))}
        <span className="spacer" />
        <button className="btn primary" disabled={busy} onClick={submit}>
          {busy ? '求解中…' : '定位（精确求解）'}
        </button>
        {result && <button className="btn" onClick={clearResult}>清除结果</button>}
      </div>

      <div className="layout">
        <div className="pane pane-editor">
          <NetworkEditor draft={draft} setDraft={setDraft} errors={errors} />
        </div>
        <div className="pane pane-viz">
          <div className="graph-card">
            <NetworkGraph draft={draft} result={result} highlightSensors={highlight} />
            {result && (
              <div className="graph-legend">
                <span><i className="lg pipe-lg" />管段（#序号 · 长度）</span>
                <span><i className="lg interval-lg" />同优闭区间</span>
                <span><i className="lg point-lg" />同优点</span>
                <span><i className="lg source-lg" />规范源点</span>
                <span><i className="lg sensor-lg" />传感器（数字为编号）</span>
              </div>
            )}
          </div>
          {result && (
            <ResultPanel
              result={result}
              onHighlight={setHighlight}
              clearHighlight={() => setHighlight([])}
            />
          )}
          {!result && errors.length === 0 && (
            <div className="placeholder">
              编辑左侧节点、管段与传感器的整数到达时刻，点击「定位」。
              成功后这里会显示规范源点、全部同优位置与各传感器的精确残差；
              校验失败时草稿不会被修改，错误会定位到具体的行与字段。
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
