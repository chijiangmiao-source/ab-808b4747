import React from 'react'

function Frac({ f }) {
  if (!f) return null
  return <span className="frac" title={`精确有理数 ${f.num}/${f.den}`}>{f.text}</span>
}

export default function ResultPanel({ result, onHighlight, clearHighlight }) {
  const [selectedOpt, setSelectedOpt] = React.useState(0)
  if (!result) return null

  const { canonical, optima, residuals, witnesses, optimal_value } = result
  const opt = optima[Math.min(selectedOpt, optima.length - 1)]

  const posSet = new Set(witnesses.positive)
  const negSet = new Set(witnesses.negative)

  return (
    <div className="result-panel">
      <section className="summary-cards">
        <div className="card">
          <div className="card-label">最优最大绝对残差 r*</div>
          <div className="card-value"><Frac f={optimal_value} /></div>
        </div>
        <div className="card highlight-card">
          <div className="card-label">规范源点</div>
          <div className="card-value small">
            管段 #{canonical.edge_index}（{canonical.from_node} → {canonical.to_node}，长 {canonical.length}）
          </div>
          <div className="card-sub">
            从首端 {canonical.from_node} 量起 x = <Frac f={canonical.coordinate} />，发声时刻 t₀ = <Frac f={canonical.emission_time} />
          </div>
        </div>
        <div className="card">
          <div className="card-label">同优位置数</div>
          <div className="card-value">{optima.length}</div>
          <div className="card-sub">
            {optima.every((o) => o.point) ? '全部为孤立点' : optima.some((o) => !o.point) ? '含一个或多个闭区间' : ''}
          </div>
        </div>
      </section>

      <section>
        <h3>全部同优位置（按管段输入次序）</h3>
        <div className="optima-list">
          {optima.map((o, i) => (
            <button
              key={i}
              className={`chip ${i === Math.min(selectedOpt, optima.length - 1) ? 'chip-active' : ''}`}
              onMouseEnter={() => onHighlight?.([])}
              onClick={() => setSelectedOpt(i)}
            >
              #{o.edge_index}: {o.from_node}→{o.to_node} ·{' '}
              {o.point ? (
                <>x = <Frac f={o.coordinate_start} /></>
              ) : (
                <>x ∈ [<Frac f={o.coordinate_start} />, <Frac f={o.coordinate_end} />]</>
              )}
              {o.edge_index === canonical.edge_index && <em className="canon-tag">含规范点</em>}
            </button>
          ))}
        </div>
        {opt && !opt.point && (
          <div className="interval-note">
            该闭区间上任一点都达到 r*；区间内最优发声时刻随位置线性变化：
            {opt.t0_segments.map((seg, i) => (
              <div key={i} className="seg">
                x ∈ [<Frac f={seg.x_start} />, <Frac f={seg.x_end} />] 时，
                t₀ ∈ [<Frac f={seg.t0_start} />, <Frac f={seg.t0_end} />]
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3>
          各传感器残差
          <span className="witness-legend">
            <span className="dot pos-dot" /> 正极值 +r*
            <span className="dot neg-dot" /> 负极值 −r*（最优性证据）
          </span>
        </h3>
        <table className="residual-table">
          <thead>
            <tr>
              <th>#</th><th>节点</th><th>观测 t</th><th>精确距离</th>
              <th>预测时刻</th><th>残差</th><th>|残差|</th>
            </tr>
          </thead>
          <tbody>
            {residuals.map((r) => {
              const cls = r.extremal === 'positive'
                ? 'row-pos'
                : r.extremal === 'negative' ? 'row-neg' : ''
              return (
                <tr
                  key={r.sensor_index}
                  className={cls}
                  onMouseEnter={() => onHighlight?.([r.sensor_index])}
                  onMouseLeave={() => clearHighlight?.()}
                >
                  <td>{r.sensor_index}</td>
                  <td>{r.node}</td>
                  <td>{r.observed}</td>
                  <td><Frac f={r.distance} /></td>
                  <td><Frac f={r.predicted} /></td>
                  <td><Frac f={r.residual} /></td>
                  <td><Frac f={r.abs_residual} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <div className="evidence">
          {optimal_value.num === 0 ? (
            <>r* = 0：存在 <strong>{witnesses.positive.length}</strong> 个传感器在规范点同时达到 0 残差，数据被模型精确解释。</>
          ) : (
            <>
              达到正极值的传感器：
              <strong onMouseEnter={() => onHighlight?.(witnesses.positive)} onMouseLeave={clearHighlight}>
                {witnesses.positive.length ? witnesses.positive.join(', ') : '—'}
              </strong>
              ；达到负极值的传感器：
              <strong onMouseEnter={() => onHighlight?.(witnesses.negative)} onMouseLeave={clearHighlight}>
                {witnesses.negative.length ? witnesses.negative.join(', ') : '—'}
              </strong>
              。<span className="hint">两者同时存在即证明 r* 无法再下降。</span>
            </>
          )}
        </div>
      </section>
    </div>
  )
}
