import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const api = async (path, options = {}) => {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "请求失败");
  return payload;
};

function App() {
  const [text, setText] = useState("Query → Retriever → Generator → Answer");
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
    <header><p className="eyebrow">SCIENTIFIC FIGURE AGENT</p><h1>把论文方法变成可编辑科研图</h1><p className="muted">本地优先的 Figure Contract、候选方案和证据追踪工作流。</p></header>
    <section className="card input-card"><label htmlFor="method">论文段落或方法链</label><textarea id="method" value={text} onChange={(event) => setText(event.target.value)} /><button disabled={busy || !text.trim()} onClick={run}>{busy ? "正在生成…" : "分析并生成 3 个候选"}</button>{error && <p className="error">{error}</p>}</section>
    {task && <section className="status"><span>任务 {task.task_id.slice(0, 8)}</span><strong>{task.status}</strong></section>}
    {contract && <section className="card"><h2>Figure Contract</h2><div className="chips"><span>{contract.target_figure_type}</span><span>{contract.required_labels.length} 个节点</span><span>{contract.required_edges.length} 条边</span></div><p className="muted">证据覆盖率：{contract.evidence_coverage}</p></section>}
    {candidates.length > 0 && <section><h2>候选方案</h2><div className="grid">{candidates.map((candidate) => <article className={`candidate ${selected === candidate.candidate_id ? "selected" : ""}`} key={candidate.candidate_id}><div className="candidate-head"><h3>{candidate.candidate_id}</h3><span>{candidate.scores?.structural_validity ?? "—"}</span></div>{(candidate.artifacts?.png || candidate.artifacts?.svg) && <img src={candidate.artifacts.png || candidate.artifacts.svg} alt="候选预览" onError={(event) => { event.currentTarget.style.display = "none"; }} />}<p className="muted">结构、版式和视觉层级候选均保留原始 Figure Spec。</p><button onClick={() => exportCandidate(candidate.candidate_id)}>选择并导出</button></article>)}</div></section>}
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
