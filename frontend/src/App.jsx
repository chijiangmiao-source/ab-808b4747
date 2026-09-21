import { useEffect, useMemo, useState } from "react";
import { locate, getHealth } from "./api";
import { sampleDraft, emptyDraft } from "./sample";
import NetworkSvg from "./NetworkSvg";

const DRAFT_KEY = "leak-audit-draft-v1";

function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return sampleDraft();
}

export default function App() {
  const [draft, setDraft] = useState(loadDraft);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState("checking");
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [runSeq, setRunSeq] = useState(0);

  useEffect(() => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [draft]);

  useEffect(() => {
    getHealth().then(() => setHealth("ok")).catch(() => setHealth("down"));
  }, []);

  // Error targeting: edges[i].field / sensors[i].field
  const errMap = useMemo(() => {
    const m = new Map();
    for (const e of errors) {
      const key =
        e.edge_index !== undefined ? `edge:${e.edge_index}:${e.field ?? ""}`
        : e.sensor_index !== undefined ? `sensor:${e.sensor_index}:${e.field ?? ""}`
        : `global:${e.field ?? ""}`;
      if (!m.has(key)) m.set(key, e.message);
    }
    return m;
  }, [errors]);

  const cellErr = (kind, i, field) =>
    errMap.get(`${kind}:${i}:${field}`) ?? errMap.get(`${kind}:${i}:`);

  const updateEdge = (i, patch) => {
    setDraft((d) => ({
      ...d,
      edges: d.edges.map((e, j) => (j === i ? { ...e, ...patch } : e)),
    }));
    setResult(null);
  };
  const updateSensor = (i, patch) => {
    setDraft((d) => ({
      ...d,
      sensors: d.sensors.map((s, j) => (j === i ? { ...s, ...patch } : s)),
    }));
    setResult(null);
  };

  const addEdge = () =>
    setDraft((d) => ({
      ...d,
      edges: [...d.edges, { id: `P${d.edges.length + 1}`, from: "", to: "", length: 1 }],
    }));
  const removeEdge = (i) =>
    setDraft((d) => ({ ...d, edges: d.edges.filter((_, j) => j !== i) }));
  const addSensor = () =>
    setDraft((d) => ({
      ...d,
      sensors: [...d.sensors,
                { id: `S${d.sensors.length + 1}`, node: "", arrival: 0 }],
    }));
  const removeSensor = (i) =>
    setDraft((d) => ({ ...d, sensors: d.sensors.filter((_, j) => j !== i) }));

  const run = async () => {
    setLoading(true);
    setErrors([]);
    setResult(null);
    try {
      // Serialize numeric cells: invalid text stays in the draft so the
      // backend reports it and the user sees exactly what they typed.
      const payload = {
        edges: draft.edges.map((e) => ({
          id: e.id, from: e.from, to: e.to,
          length: e.length === "" || Number.isNaN(Number(e.length))
                  ? e.length : Number(e.length),
        })),
        sensors: draft.sensors.map((s) => ({
          id: s.id, node: s.node,
          arrival: s.arrival === "" || Number.isNaN(Number(s.arrival))
                    ? s.arrival : Number(s.arrival),
        })),
      };
      const r = await locate(payload);
      setResult(r);
      setRunSeq((x) => x + 1);
    } catch (e) {
      setErrors(e.errors ?? [{ code: "NETWORK", message: e.message }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>地下储气库树状管网 · 泄漏定位审计台</h1>
        <span className={`health health-${health}`}>
          API：{health === "ok" ? "● 在线" : health === "checking" ? "○ 检查中" : "● 不可用"}
        </span>
      </header>

      <section className="editors">
        <div className="panel">
          <div className="panel-head">
            <h2>管段（{draft.edges.length}）</h2>
            <div className="row-actions">
              <button onClick={addEdge}>＋ 管段</button>
              <button className="ghost" onClick={() => setDraft(sampleDraft())}>
                载入示例
              </button>
              <button className="ghost"
                      onClick={() => setDraft(emptyDraft())}>清空</button>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>#</th><th>管段 ID</th><th>首端节点</th>
                  <th>末端节点</th><th>长度(正整数)</th><th></th></tr>
              </thead>
              <tbody>
                {draft.edges.map((e, i) => (
                  <tr key={i} className={cellErr("edge", i, null) ? "row-err" : ""}>
                    <td>{i + 1}</td>
                    <Cell error={cellErr("edge", i, "id")}>
                      <input value={e.id ?? ""}
                             onChange={(ev) => updateEdge(i, { id: ev.target.value })} />
                    </Cell>
                    <Cell error={cellErr("edge", i, "from")}>
                      <input value={e.from ?? ""}
                             onChange={(ev) => updateEdge(i, { from: ev.target.value })} />
                    </Cell>
                    <Cell error={cellErr("edge", i, "to")}>
                      <input value={e.to ?? ""}
                             onChange={(ev) => updateEdge(i, { to: ev.target.value })} />
                    </Cell>
                    <Cell error={cellErr("edge", i, "length")}>
                      <input className="num" inputMode="numeric"
                             value={e.length ?? ""}
                             onChange={(ev) => updateEdge(
                               i, { length: ev.target.value })} />
                    </Cell>
                    <td><button className="del" onClick={() => removeEdge(i)}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>传感器（{draft.sensors.length}）</h2>
            <div className="row-actions">
              <button onClick={addSensor}>＋ 传感器</button>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>#</th><th>传感器 ID</th><th>所在节点</th>
                  <th>整数到达时刻</th><th></th></tr>
              </thead>
              <tbody>
                {draft.sensors.map((s, i) => (
                  <tr key={i} className={cellErr("sensor", i, null) ? "row-err" : ""}>
                    <td>{i + 1}</td>
                    <Cell error={cellErr("sensor", i, "id")}>
                      <input value={s.id ?? ""}
                             onChange={(ev) => updateSensor(i, { id: ev.target.value })} />
                    </Cell>
                    <Cell error={cellErr("sensor", i, "node")}>
                      <input list="node-list" value={s.node ?? ""}
                             onChange={(ev) => updateSensor(i, { node: ev.target.value })} />
                    </Cell>
                    <Cell error={cellErr("sensor", i, "arrival")}>
                      <input className="num" inputMode="numeric"
                             value={s.arrival ?? ""}
                             onChange={(ev) => updateSensor(
                               i, { arrival: ev.target.value })} />
                    </Cell>
                    <td><button className="del" onClick={() => removeSensor(i)}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <datalist id="node-list">
              {[...new Set(draft.edges.flatMap((e) => [e.from, e.to]))
                  .filter(Boolean)].map((n) => (
                <option key={n} value={n} />
              ))}
            </datalist>
          </div>
        </div>
      </section>

      <div className="run-bar">
        <button className="primary" disabled={loading} onClick={run}>
          {loading ? "求解中…（精确有理数）" : "▶ 运行定位"}
        </button>
        {errors.length > 0 && (
          <span className="error-summary">
            {errors.length} 个错误：草稿已保留，出错单元以红色标出
          </span>
        )}
        {result && (
          <span className="ok-summary">
            成功：最优最大残差 = <b>{result.optimal_residual.dec}</b>，
            共 {result.solution_count} 个同优位置
          </span>
        )}
      </div>

      {errors.length > 0 && (
        <section className="panel error-panel">
          <h2>校验 / 求解错误</h2>
          <ul>
            {errors.map((e, i) => (
              <li key={i}>
                <code>{e.code}</code>
                {e.target && <span className="target"> @ {e.target}</span>}
                ：{e.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel viz">
        <h2>SVG 管网（红线 = 全部同优管段，实心点 = 规范源点，加粗线段 = 同优闭区间）</h2>
        <NetworkSvg draft={draft} result={result} selectedEdge={selectedEdge}
                    onSelectEdge={setSelectedEdge} />
      </section>

      {result && <Results key={runSeq} result={result}
                          onSelectEdge={setSelectedEdge} />}

      <footer>
        后端：FastAPI + fractions 精确有理数 · 声速归一化为 1 ·
        发声时刻 t 不设先验，按区间中点取规范值
      </footer>
    </div>
  );
}

function Cell({ error, children }) {
  return (
    <td className={error ? "cell-err" : ""} title={error ?? ""}>
      {children}
      {error && <div className="cell-msg">{error}</div>}
    </td>
  );
}

function Results({ result, onSelectEdge }) {
  const [shown, setShown] = useState(0);
  const idx = Math.min(shown, result.solutions.length - 1);
  const sol = result.solutions[idx];

  return (
    <section className="panel results">
      <h2>定位结果</h2>
      <div className="summary-grid">
        <Stat label="节点数" value={result.node_count} />
        <Stat label="管段数" value={result.edge_count} />
        <Stat label="传感器数" value={result.sensor_count} />
        <Stat label="最优最大绝对残差 R*" value={result.optimal_residual.dec}
              exact={`${result.optimal_residual.n}/${result.optimal_residual.d}`}
              highlight />
        <Stat label="同优位置数" value={result.solution_count} />
        <Stat label="求解耗时" value={`${result.elapsed_ms ?? "-"} ms`} />
      </div>

      {result.solutions.length > 1 && (
        <div className="sol-tabs">
          {result.solutions.map((s, i) => (
            <button key={i} className={i === idx ? "tab active" : "tab"}
                    onClick={() => { setShown(i); onSelectEdge(s.edge_index); }}>
              {i + 1}. {s.edge_id} @ {s.coordinate.dec}
            </button>
          ))}
        </div>
      )}

      <div className="solution">
        <h3>规范源点 #{idx + 1}（按管段输入次序 → 首端坐标 → 发声时刻排序）</h3>
        <div className="summary-grid">
          <Stat label="管段" value={`${sol.edge_id}（${sol.from_node} → ${sol.to_node}，长 ${sol.edge_length}）`} />
          <Stat label="距首端坐标" value={sol.coordinate.dec}
                exact={`${sol.coordinate.n}/${sol.coordinate.d}`} />
          <Stat label="同优闭区间"
                value={sol.interval.degenerate
                  ? `{ ${sol.interval.start.dec} }（单点）`
                  : `[ ${sol.interval.start.dec}, ${sol.interval.end.dec} ]`} />
          <Stat label="规范发声时刻 t*" value={sol.time.dec}
                exact={`${sol.time.n}/${sol.time.d}`} />
        </div>

        <div className="witnesses">
          <div className="wit wit-pos">
            <b>达到 +R* 的传感器（正极值证据）：</b>
            {sol.positive_witnesses.length
              ? sol.positive_witnesses.join("、")
              : "（无，理论上不应出现）"}
          </div>
          <div className="wit wit-neg">
            <b>达到 −R* 的传感器（负极值证据）：</b>
            {sol.negative_witnesses.length
              ? sol.negative_witnesses.join("、")
              : "（无）"}
          </div>
        </div>

        <h3>各传感器残差（观测 − (t* + 距离)）</h3>
        <div className="table-wrap">
          <table className="resid-table">
            <thead>
              <tr><th>传感器</th><th>节点</th><th>观测时刻</th>
                <th>预测时刻</th><th>残差</th><th>证据</th></tr>
            </thead>
            <tbody>
              {sol.sensor_residuals.map((r) => (
                <tr key={r.sensor_id}
                    className={r.sign > 0 ? "res-pos" : r.sign < 0 ? "res-neg" : ""}>
                  <td>{r.sensor_id}</td>
                  <td>{r.node}</td>
                  <td className="num">{r.observed}</td>
                  <td className="num">{r.predicted.dec}</td>
                  <td className="num">{r.residual.dec}</td>
                  <td>{r.witness === "+" ? "▲ +R*" : r.witness === "-" ? "▼ −R*" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, exact, highlight }) {
  return (
    <div className={`stat ${highlight ? "stat-hl" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {exact && exact !== value && <div className="stat-exact">{exact}</div>}
    </div>
  );
}
