import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { resolvePreview } from "./preview.js";
import "./styles.css";

const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "请求失败");
  return payload;
};

function ScoreBar({ label, value }) {
  const percent = Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100);
  return <div className="score-row"><span>{label}</span><div className="score-track"><i style={{ width: `${percent}%` }} /></div><strong>{percent}%</strong></div>;
}

function ArtifactLinks({ artifacts }) {
  return <div className="artifact-links">{Object.entries(artifacts || {}).filter(([, url]) => url).map(([kind, url]) => <a key={kind} href={url} target="_blank" rel="noreferrer">下载 {kind.toUpperCase()}</a>)}</div>;
}

function EvidencePanel({ candidate }) {
  const nodes = candidate.spec?.nodes || [];
  return <details className="evidence-panel"><summary>查看节点证据（{nodes.length}）</summary><div className="evidence-list">{nodes.map((node) => <div className="evidence-item" key={node.id}><strong>{node.label}</strong><span>{node.evidence?.[0]?.quote || "暂无引用，需要人工审阅"}</span></div>)}</div></details>;
}

function CandidateCard({ candidate, selected, onExport }) {
  const [previewError, setPreviewError] = useState(false);
  const preview = resolvePreview(candidate.artifacts);
  return <article className={`candidate ${selected ? "selected" : ""}`}>
    <div className="candidate-head"><div><span className="family-tag">{candidate.design?.family || "diagram"}</span><h3>{candidate.candidate_id}</h3></div><span className="score-badge">{Math.round((candidate.scores?.structural_validity ?? 0) * 100)}%</span></div>
    <div className="candidate-preview">{preview.url && !previewError ? <img src={preview.url} alt={`${candidate.candidate_id} 预览`} onError={() => setPreviewError(true)} /> : <div className="preview-fallback">预览不可用<br /><small>可下载 SVG / PDF / Draw.io 源文件</small></div>}</div>
    <div className="design-copy"><strong>{candidate.design?.rationale}</strong><span>适合：{(candidate.design?.best_for || []).join("、")}</span><span>取舍：{(candidate.design?.tradeoffs || []).join("；")}</span></div>
    <div className="scores"><ScoreBar label="证据" value={candidate.scores?.evidence_coverage} /><ScoreBar label="可读性" value={candidate.scores?.visual_readability ?? candidate.scores?.readability} /><ScoreBar label="差异度" value={candidate.scores?.layout_distinctiveness ?? 0.7} /></div>
    <EvidencePanel candidate={candidate} />
    <ArtifactLinks artifacts={candidate.artifacts} />
    <button onClick={() => onExport(candidate.candidate_id)}>选择并导出</button>
  </article>;
}

function App() {
  const [text, setText] = useState("用户问题经过规划器分解，检索器查询知识库，工具返回证据，生成器综合证据后输出答案；若证据不足，则回到检索器继续搜索。");
  const [task, setTask] = useState(null);
  const [contract, setContract] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true); setError("");
    try {
      const created = await api("/api/tasks", { method: "POST", body: JSON.stringify({ input_type: "paper_text", content: text, candidate_count: 3 }) });
      setTask(created);
      const analyzed = await api(`/api/tasks/${created.task_id}/analyze`, { method: "POST" });
      setContract(analyzed.contract);
      const generated = await api(`/api/tasks/${created.task_id}/generate-candidates`, { method: "POST" });
      setCandidates(generated.candidates || []);
      setSelected("");
      setTask(await api(`/api/tasks/${created.task_id}`));
    } catch (exc) { setError(exc.message); }
    finally { setBusy(false); }
  }

  async function exportCandidate(candidateId) {
    setError("");
    try {
      await api(`/api/tasks/${task.task_id}/select-candidate`, { method: "POST", body: JSON.stringify({ candidate_id: candidateId }) });
      const result = await api(`/api/tasks/${task.task_id}/export`, { method: "POST", body: JSON.stringify({ candidate_id: candidateId }) });
      setSelected(candidateId);
      window.open(result.download_url, "_blank");
    } catch (exc) { setError(exc.message); }
  }

  return <main className="shell">
    <header><p className="eyebrow">SCIENTIFIC FIGURE AGENT</p><h1>把论文方法变成可编辑科研图</h1><p className="muted">先理解证据，再比较三种版式和视觉层级。所有候选都保留 SVG、PDF 和 Draw.io 源文件。</p></header>
    <section className="card input-card"><label htmlFor="method">论文段落或方法链</label><textarea id="method" value={text} onChange={(event) => setText(event.target.value)} /><button disabled={busy || !text.trim()} onClick={run}>{busy ? "正在生成…" : "分析并生成 3 个候选"}</button>{error && <p className="error">{error}</p>}</section>
    {task && <section className="status"><span>任务 {task.task_id.slice(0, 8)}</span><strong>{task.status}</strong></section>}
    {contract && <section className="card contract"><div><p className="eyebrow">FIGURE CONTRACT</p><h2>{contract.target_figure_type}</h2></div><div className="chips"><span>{contract.required_labels?.length || 0} 个节点</span><span>{contract.required_edges?.length || 0} 条边</span><span>证据覆盖率 {contract.evidence_coverage}</span></div></section>}
    {candidates.length > 0 && <section><div className="section-heading"><div><p className="eyebrow">DESIGN OPTIONS</p><h2>候选方案</h2></div><p className="muted">三种方案表达同一份语义，视觉取舍各不相同。</p></div><div className="grid">{candidates.map((candidate) => <CandidateCard key={candidate.candidate_id} candidate={candidate} selected={selected === candidate.candidate_id} onExport={exportCandidate} />)}</div></section>}
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
