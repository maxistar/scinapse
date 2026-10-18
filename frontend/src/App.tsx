import { useEffect, useRef, useState } from 'react';
import example from '../../graph.json';
import GraphExplorer from './GraphExplorer';
import ResearchSetup from './ResearchSetup';
import { buildRequest, getGraph, getResearch, startResearch, type ResearchJob } from './api';
import type { GraphData } from './graph';
import type { ResearchSession } from './research';

const exampleGraph = example as unknown as GraphData;
const sessionKey = 'scinapse-active-research:v1';
interface ActiveSession { jobId?: string; mode?: 'example'; input: ResearchSession }
function restore(): ActiveSession | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(sessionKey) || 'null');
    return value && (value.mode === 'example' || /^[a-f0-9]{32}$/.test(value.jobId)) && typeof value.input?.query === 'string' && Array.isArray(value.input.seedIds) && Array.isArray(value.input.references) ? value : null;
  } catch { return null; }
}
function remember(session: ActiveSession | null) {
  try { if (session) sessionStorage.setItem(sessionKey, JSON.stringify(session)); else sessionStorage.removeItem(sessionKey); } catch { /* Current session remains usable. */ }
}
export default function App() {
  const [active, setActive] = useState<ActiveSession | null>(restore);
  const [graph, setGraph] = useState<GraphData | null>(() => restore()?.mode === 'example' ? exampleGraph : null);
  const [job, setJob] = useState<ResearchJob | null>(null);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const busy = starting || (!!active?.jobId && !graph && !error);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!active?.jobId) return;
    const polling = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const status = await getResearch(active!.jobId!, polling.signal);
        if (polling.signal.aborted) return;
        setJob(status);
        if (status.status === 'failed') { setError(status.message); return; }
        if (status.status === 'completed') {
          const result = await getGraph(active!.jobId!, polling.signal);
          if (!polling.signal.aborted) setGraph(result);
        } else timer = setTimeout(poll, 1500);
      } catch (cause) { if (!polling.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load research. Please retry.'); }
    }
    void poll();
    return () => { polling.abort(); clearTimeout(timer); };
  }, [active]);
  async function submit(input: ResearchSession) {
    const body = buildRequest(input, exampleGraph.nodes);
    controller.current?.abort();
    const submission = new AbortController(); controller.current = submission;
    remember(null); setActive(null); setStarting(true); setError(''); setJob(null);
    try {
      const created = await startResearch(body, submission.signal);
      if (submission.signal.aborted) return;
      const session = { input, jobId: created.id };
      remember(session); setActive(session); setJob(created); setGraph(null);
    } catch (cause) {
      if (!submission.signal.aborted) throw cause;
    } finally { if (!submission.signal.aborted) setStarting(false); }
  }
  function openExample() {
    controller.current?.abort(); setStarting(false); setError(''); setJob(null);
    const session: ActiveSession = { mode: 'example', input: { query: exampleGraph.research_question, seedIds: exampleGraph.nodes.filter(p => p.is_seed).map(p => p.id), references: [] } };
    remember(session); setActive(session); setGraph(exampleGraph);
  }
  function newSearch() {
    controller.current?.abort(); remember(null); setActive(null); setGraph(null); setError(''); setJob(null); setStarting(false);
  }
  if (graph) return <GraphExplorer key={`${active?.jobId ?? 'example'}:${graph.exploration_id}`} data={graph} research={active?.input ?? null} onNewSearch={newSearch} />;
  return <ResearchSetup papers={exampleGraph.nodes} initial={active?.input} onSubmit={submit} onExample={openExample} busy={busy} job={job} error={error} onBack={newSearch} />;
}
