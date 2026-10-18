import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Clock3, Download, History, RefreshCw, X } from 'lucide-react';
import { getGraph, listResearch, type ResearchJob } from './api';

interface Props { onClose: () => void; onOpen: (task: ResearchJob) => void; onStart: () => void }
const labels = { queued: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed' };
export default function ResearchHistory({ onClose, onOpen, onStart }: Props) {
  const [tasks, setTasks] = useState<ResearchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const [filter, setFilter] = useState('all');
  const [refresh, setRefresh] = useState(0);
  const [downloading, setDownloading] = useState<string | null>(null);
  const panel = useRef<HTMLElement>(null);
  const downloadController = useRef<AbortController | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLButtonElement>('[aria-label="Close research history"]')?.focus();
    return () => { downloadController.current?.abort(); if (previous?.isConnected && !previous.closest('[inert]')) previous.focus(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function update() {
      let delay = 5000;
      try {
        const result = await listResearch(controller.signal);
        if (!controller.signal.aborted) { setTasks(result.tasks); setError(''); }
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load research history.');
        delay = 10000;
      } finally {
        if (!controller.signal.aborted) { setLoading(false); timer = setTimeout(update, delay); }
      }
    }
    void update();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);
  async function download(task: ResearchJob) {
    downloadController.current?.abort();
    const controller = new AbortController(); downloadController.current = controller;
    setDownloading(task.id); setDownloadError('');
    try {
      const graph = await getGraph(task.id, controller.signal);
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `scinapse-${task.id}.json`; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      if (!controller.signal.aborted) setDownloadError(cause instanceof Error ? cause.message : 'Could not download the graph.');
    } finally { if (!controller.signal.aborted) setDownloading(null); }
  }
  const visible = tasks.filter(task => filter === 'all' || task.status === filter);
  return <div className="history-backdrop" onClick={onClose}>
    <section ref={panel} className="history-panel" role="dialog" aria-modal="true" aria-labelledby="history-title" onClick={event => event.stopPropagation()} onKeyDown={event => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
      if (event.key === 'Tab') {
        const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), select, a[href]')];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }}>
      <header className="history-header"><div><History size={20} /><h2 id="history-title">Research history</h2></div><button className="icon-button" aria-label="Close research history" onClick={onClose}><X size={19} /></button></header>
      <div className="history-toolbar"><label><span className="sr-only">Filter research status</span><select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All research</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="text-button" onClick={() => setRefresh(value => value + 1)} aria-label="Refresh research history"><RefreshCw size={13} />Refresh</button></div>
      {(error || downloadError) && <p className="history-error" role="alert">{error || downloadError}</p>}
      <div className="history-content">
        {loading ? <p className="history-empty" role="status">Loading your research…</p> : !visible.length ? <div className="history-empty"><History size={27} /><h3>{error ? 'History is unavailable' : tasks.length ? 'No matching research' : 'Your research starts here'}</h3><p>{error ? 'Check the server connection or try Refresh.' : tasks.length ? 'Choose another status to see more tasks.' : 'Start with a question and a paper. Your tasks will appear here.'}</p>{!tasks.length && !error && <button className="button primary" onClick={onStart}>Start research<ArrowRight size={14} /></button>}</div> : <ul className="history-list">{visible.map(task => <li key={task.id}>
          <div className="history-task-top"><h3>{task.question}</h3><span className={`task-status task-${task.status}`}>{task.status === 'completed' ? <Check size={12} /> : task.status === 'failed' ? <X size={12} /> : task.status === 'running' ? <span className="task-spinner" /> : <Clock3 size={12} />}{labels[task.status]}</span></div>
          <time dateTime={new Date(task.created_at * 1000).toISOString()}>{new Date(task.created_at * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</time>
          {(task.status === 'running' || task.status === 'queued') && <p className="history-progress">Stage {task.stage} of {task.total_stages} · {task.message}</p>}
          {task.status === 'failed' && <p className="history-failure">{task.message}</p>}
          <div className="history-actions">{task.status === 'completed' ? <><button className="button secondary" onClick={() => onOpen(task)}>Open graph<ArrowRight size={13} /></button><button className="text-button" disabled={downloading !== null} onClick={() => void download(task)} aria-label={`Download JSON for ${task.question}`}><Download size={13} />{downloading === task.id ? 'Downloading…' : 'Download JSON'}</button></> : task.status !== 'failed' && <button className="text-button" onClick={() => onOpen(task)}>View progress<ArrowRight size={13} /></button>}</div>
        </li>)}</ul>}
      </div>
      <footer>Updates automatically · Up to 20 tasks · History clears when the server restarts</footer>
    </section>
  </div>;
}
