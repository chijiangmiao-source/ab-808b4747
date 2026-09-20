import React from 'react'

function rowHasError(errorMap, kind, index, field) {
  const list = errorMap.get(`${kind}:${index}`)
  if (!list) return false
  return field ? list.some((e) => e.field === field) : true
}

function RowError({ errorMap, kind, index }) {
  const list = errorMap.get(`${kind}:${index}`)
  if (!list || list.length === 0) return null
  return (
    <div className="row-error">
      {list.map((e, i) => (
        <span key={i}>{i > 0 ? '；' : ''}
          {e.field ? `[${e.field}] ` : ''}
          {e.message}
        </span>
      ))}
    </div>
  )
}

function inputClass(errorMap, kind, index, field) {
  return rowHasError(errorMap, kind, index, field) ? 'cell-input invalid' : 'cell-input'
}

export default function NetworkEditor({ draft, setDraft, errors }) {
  const errorMap = React.useMemo(() => {
    const m = new Map()
    for (const e of errors || []) {
      if (e.index == null) continue
      const key = `${e.kind}:${e.index}`
      if (!m.has(key)) m.set(key, [])
      m.get(key).push(e)
    }
    return m
  }, [errors])

  const globalErrors = (errors || []).filter((e) => e.index == null)

  const update = (section, index, field, value) => {
    const next = structuredClone(draft)
    next[section][index][field] = value
    setDraft(next)
  }

  const addRow = (section, row) => {
    const next = structuredClone(draft)
    next[section].push({ ...row })
    setDraft(next)
  }

  const removeRow = (section, index) => {
    const next = structuredClone(draft)
    next[section].splice(index, 1)
    setDraft(next)
  }

  return (
    <div className="editor">
      {globalErrors.length > 0 && (
        <div className="global-errors">
          {globalErrors.map((e, i) => (
            <div key={i}>
              <b>网络级错误：</b>
              {e.message}
            </div>
          ))}
        </div>
      )}

      <section className="table-section">
        <header>
          <h3>节点 <span className="hint">2 – 2000 个，整数编号</span></h3>
          <button className="btn small" onClick={() => addRow('nodes', { id: '' })}>+ 节点</button>
        </header>
        <table>
          <thead><tr><th style={{ width: 54 }}>#</th><th>编号</th><th style={{ width: 40 }}></th></tr></thead>
          <tbody>
            {draft.nodes.map((node, i) => {
              const raw = typeof node === 'object' ? node.id : node
              return (
                <React.Fragment key={i}>
                  <tr className={rowHasError(errorMap, 'node', i) ? 'row-invalid' : ''}>
                    <td className="row-index">{i}</td>
                    <td>
                      <input
                        className={inputClass(errorMap, 'node', i, 'id')}
                        value={raw}
                        inputMode="numeric"
                        onChange={(ev) => {
                          const next = structuredClone(draft)
                          next.nodes[i] = ev.target.value
                          setDraft(next)
                        }}
                      />
                    </td>
                    <td><button className="btn ghost" title="删除" onClick={() => removeRow('nodes', i)}>×</button></td>
                  </tr>
                  <tr><td colSpan={3}><RowError errorMap={errorMap} kind="node" index={i} /></td></tr>
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </section>

      <section className="table-section">
        <header>
          <h3>管段 <span className="hint">正整数长度，须恰好构成树</span></h3>
          <button className="btn small" onClick={() => addRow('edges', { u: '', v: '', length: '' })}>+ 管段</button>
        </header>
        <table>
          <thead><tr><th style={{ width: 54 }}>#</th><th>首端 u</th><th>末端 v</th><th>长度</th><th style={{ width: 40 }}></th></tr></thead>
          <tbody>
            {draft.edges.map((edge, i) => (
              <React.Fragment key={i}>
                <tr className={rowHasError(errorMap, 'edge', i) ? 'row-invalid' : ''}>
                  <td className="row-index">{i}</td>
                  <td><input className={inputClass(errorMap, 'edge', i, 'u')} value={edge.u} inputMode="numeric"
                    onChange={(e) => update('edges', i, 'u', e.target.value)} /></td>
                  <td><input className={inputClass(errorMap, 'edge', i, 'v')} value={edge.v} inputMode="numeric"
                    onChange={(e) => update('edges', i, 'v', e.target.value)} /></td>
                  <td><input className={inputClass(errorMap, 'edge', i, 'length')} value={edge.length} inputMode="numeric"
                    onChange={(e) => update('edges', i, 'length', e.target.value)} /></td>
                  <td><button className="btn ghost" title="删除" onClick={() => removeRow('edges', i)}>×</button></td>
                </tr>
                <tr><td colSpan={5}><RowError errorMap={errorMap} kind="edge" index={i} /></td></tr>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </section>

      <section className="table-section">
        <header>
          <h3>传感器 <span className="hint">2 – 128 个，位于不同节点；整数到达时刻</span></h3>
          <button className="btn small" onClick={() => addRow('sensors', { node: '', time: '' })}>+ 传感器</button>
        </header>
        <table>
          <thead><tr><th style={{ width: 54 }}>#</th><th>节点</th><th>到达时刻 t</th><th style={{ width: 40 }}></th></tr></thead>
          <tbody>
            {draft.sensors.map((s, i) => (
              <React.Fragment key={i}>
                <tr className={rowHasError(errorMap, 'sensor', i) ? 'row-invalid' : ''}>
                  <td className="row-index">{i}</td>
                  <td><input className={inputClass(errorMap, 'sensor', i, 'node')} value={s.node} inputMode="numeric"
                    onChange={(e) => update('sensors', i, 'node', e.target.value)} /></td>
                  <td><input className={inputClass(errorMap, 'sensor', i, 'time')} value={s.time} inputMode="numeric"
                    onChange={(e) => update('sensors', i, 'time', e.target.value)} /></td>
                  <td><button className="btn ghost" title="删除" onClick={() => removeRow('sensors', i)}>×</button></td>
                </tr>
                <tr><td colSpan={4}><RowError errorMap={errorMap} kind="sensor" index={i} /></td></tr>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
