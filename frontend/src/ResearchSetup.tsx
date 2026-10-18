import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Check, ChevronDown, FileText, History, Network, Plus, Search, X } from 'lucide-react';
import type { Paper } from './graph';
import { buildRequest, normalizeDoi, type ResearchJob } from './api';
import { findPapers, normalizeResearch, type ResearchSession } from './research';

interface Props {
  papers: Paper[];
  initial?: ResearchSession;
  onSubmit: (value: ResearchSession) => Promise<void>;
  onExample: () => void;
  onHistory: () => void;
  onBack: () => void;
  busy: boolean; job: ResearchJob | null; error: string;
}

export default function ResearchSetup({ papers, initial, onSubmit, onExample, onHistory, onBack, busy, job, error }: Props) {
  const [query, setQuery] = useState(initial?.query ?? '');
  const [seedIds, setSeedIds] = useState<string[]>(initial?.seedIds ?? []);
  const [references, setReferences] = useState<string[]>(initial?.references ?? []);
  const [input, setInput] = useState('');
  const [message, setMessage] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [showPapers, setShowPapers] = useState(!!initial?.references.length || !!initial?.seedIds.length);
  const queryRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const matches = useMemo(() => findPapers(papers, input, seedIds), [papers, input, seedIds]);
  const pending = input.trim();
  const exactMatch = papers.find(p => [p.id, p.url, p.title].some(value => value.toLowerCase() === pending.toLowerCase()));
  const hasInput = !!query.trim() || seedIds.length > 0 || references.length > 0 || !!pending;
  const duplicate = references.some(ref => ref.toLowerCase() === pending.toLowerCase()) || papers.some(p => seedIds.includes(p.id) && [p.title, p.url, p.id].some(v => v.toLowerCase() === pending.toLowerCase()));
  useEffect(() => { queryRef.current?.focus(); }, []);
  function addReference() {
    if (!pending) return;
    if (duplicate) { setMessage('This paper is already added.'); return; }
    if (!exactMatch && !normalizeDoi(pending)) { setMessage('Use a DOI or doi.org link. Title search only matches the example collection.'); return; }
    if (exactMatch) { setSeedIds(ids => [...ids, exactMatch.id]); setMessage('Starting paper added.'); }
    else { setReferences(refs => [...refs, normalizeDoi(pending)!]); setMessage('Starting DOI added.'); }
    setInput(''); inputRef.current?.focus();
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = normalizeResearch({ query, seedIds: pending && !duplicate && exactMatch ? [...seedIds, exactMatch.id] : seedIds, references: pending && !duplicate && !exactMatch ? [...references, pending] : references }, papers.map(p => p.id));
    if (!value) return;
    setSubmitError('');
    try { buildRequest(value, papers); await onSubmit(value); }
    catch (cause) { setSubmitError(cause instanceof Error ? cause.message : 'Could not start research. Please retry.'); setShowPapers(true); }
  }
  return <main className="research-page">
    <section className="research-search" aria-label="Research search">
      <h1 className="search-wordmark"><Network aria-hidden="true" /><span>scinapse<span>.</span></span></h1>
      <p className="search-tagline">Follow the connections. Discover what’s next.</p>
      <form onSubmit={submit} aria-label="Start research">
        <fieldset className="search-fields" disabled={busy}>
        <label className="sr-only" htmlFor="research-query">Research query</label>
        <div className="query-search"><Search size={20} aria-hidden="true" /><input ref={queryRef} id="research-query" type="text" maxLength={2000} value={query} onChange={event => { setQuery(event.target.value); setSubmitError(''); }} placeholder="What are you researching?" autoComplete="off" /><button type="submit" disabled={!hasInput} aria-label="Search research" title="Search research"><ArrowRight size={21} /></button></div>
        <div className="search-shortcuts"><button type="button" className={`add-seeds ${showPapers ? 'expanded' : ''}`} aria-expanded={showPapers} aria-controls="starting-papers" onClick={() => setShowPapers(open => !open)}><Plus size={14} />Starting papers{seedIds.length + references.length > 0 && <span>{seedIds.length + references.length}</span>}<ChevronDown size={12} /></button><button type="button" className="sample-research" onClick={onExample}>Open example graph<ArrowRight size={13} /></button></div>
        {showPapers && <section id="starting-papers" className="starting-papers" aria-label="Starting papers">
        <div className="research-label-row"><label className="research-label" htmlFor="seed-input">Starting papers</label><span>At least one DOI required</span></div>
        <div className="seed-input"><Search size={17} /><input ref={inputRef} id="seed-input" maxLength={500} value={input} onChange={event => { setInput(event.target.value); setMessage(''); }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addReference(); } }} placeholder="Paste a DOI or doi.org link" aria-describedby="seed-help" /><button type="button" disabled={!pending} aria-label="Add paper reference" onClick={addReference}><Plus size={18} /></button></div>
        {matches.length > 0 && <div className="seed-results" aria-label="Matching graph papers"><span>IN THE GENERATED GRAPH</span>{matches.map(p => <button type="button" key={p.id} onClick={() => { setSeedIds(ids => [...ids, p.id]); setInput(''); setMessage('Starting paper added.'); inputRef.current?.focus(); }}><FileText size={16} /><span><strong>{p.title}</strong><small>{p.authors[0]?.name ?? 'Author unavailable'} · {p.year ?? 'Year unknown'}</small></span><Plus size={16} /></button>)}</div>}
        <div className="seed-selected">{seedIds.map(id => { const paper = papers.find(p => p.id === id)!; return <div className="seed-chip" key={id}><Check size={16} /><span><strong>{paper.title}</strong><small>{paper.year ?? 'Year unknown'} · Retrieved paper</small></span><button type="button" onClick={() => setSeedIds(ids => ids.filter(value => value !== id))} aria-label={`Remove ${paper.title}`}><X size={15} /></button></div>; })}{references.map(ref => <div className="seed-chip pending-reference" key={ref.toLowerCase()}><FileText size={16} /><span><strong>{ref}</strong><small>DOI · Ready for discovery</small></span><button type="button" onClick={() => setReferences(refs => refs.filter(value => value !== ref))} aria-label={`Remove ${ref}`}><X size={15} /></button></div>)}</div>
        <p className="seed-help" id="seed-help">Add up to 10 DOIs. You can also select papers from the example collection.</p>
        <p className="research-status" role="status">{message}</p>
        </section>}
        </fieldset>
        {(submitError || error) && <div className="research-error" role="alert"><p>{submitError || error}</p><button type="submit" className="text-button" disabled={busy}>Retry search<ArrowRight size={13} /></button></div>}
        {busy && <section className="research-progress" role="status" aria-live="polite"><span className="research-spinner" aria-hidden="true" /><div><strong>{job?.message ?? 'Connecting to the research server'}</strong><p>{job ? `Stage ${job.stage} of ${job.total_stages} · ${job.profile === 'smoke' ? 'Quick exploration' : 'Full exploration'}` : 'Preparing your research request'}</p><small>External data providers can take several minutes.{job && !job.assessments_enabled ? ' Relevance assessment is unavailable; scores will remain unassessed.' : ''}</small></div></section>}
        {busy && <button type="button" className="text-button research-back" onClick={onBack}>Back to search · research continues on the server</button>}
      </form>
      <button type="button" className="history-link" onClick={onHistory}><History size={14} />Research history</button>
    </section>
    <p className="search-demo-note">Research from Semantic Scholar and OpenAlex · Assessments when available</p>
  </main>;
}
