import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Check, ChevronDown, FileText, Network, Plus, Search, X } from 'lucide-react';
import type { Paper } from './graph';
import { findPapers, normalizeResearch, type ResearchSession } from './research';

interface Props {
  papers: Paper[];
  sampleQuery: string;
  onSubmit: (value: ResearchSession) => void;
}

export default function ResearchSetup({ papers, sampleQuery, onSubmit }: Props) {
  const [query, setQuery] = useState('');
  const [seedIds, setSeedIds] = useState<string[]>([]);
  const [references, setReferences] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [message, setMessage] = useState('');
  const [showPapers, setShowPapers] = useState(false);
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
    if (exactMatch) { setSeedIds(ids => [...ids, exactMatch.id]); setMessage('Starting paper added.'); }
    else { setReferences(refs => [...refs, pending]); setMessage('Reference saved. Live lookup is not connected.'); }
    setInput(''); inputRef.current?.focus();
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const value = normalizeResearch({ query, seedIds: pending && !duplicate && exactMatch ? [...seedIds, exactMatch.id] : seedIds, references: pending && !duplicate && !exactMatch ? [...references, pending] : references }, papers.map(p => p.id));
    if (value) onSubmit(value);
  }
  return <main className="research-page">
    <section className="research-search" aria-label="Research search">
      <h1 className="search-wordmark"><Network aria-hidden="true" /><span>scinapse<span>.</span></span></h1>
      <p className="search-tagline">Follow the connections. Discover what’s next.</p>
      <form onSubmit={submit} aria-label="Start research">
        <label className="sr-only" htmlFor="research-query">Research query</label>
        <div className="query-search"><Search size={20} aria-hidden="true" /><input ref={queryRef} id="research-query" type="text" maxLength={2000} value={query} onChange={event => setQuery(event.target.value)} placeholder="What are you researching?" autoComplete="off" /><button type="submit" disabled={!hasInput} aria-label="Search research" title="Search research"><ArrowRight size={21} /></button></div>
        <div className="search-shortcuts"><button type="button" className={`add-seeds ${showPapers ? 'expanded' : ''}`} aria-expanded={showPapers} aria-controls="starting-papers" onClick={() => setShowPapers(open => !open)}><Plus size={14} />Starting papers{seedIds.length + references.length > 0 && <span>{seedIds.length + references.length}</span>}<ChevronDown size={12} /></button><button type="button" className="sample-research" onClick={() => onSubmit({ query: sampleQuery, seedIds: papers.filter(p => p.is_seed).map(p => p.id), references: [] })}>Try a sample search<ArrowRight size={13} /></button></div>
        {showPapers && <section id="starting-papers" className="starting-papers" aria-label="Starting papers">
        <div className="research-label-row"><label className="research-label" htmlFor="seed-input">Starting papers</label><span>Optional</span></div>
        <div className="seed-input"><Search size={17} /><input ref={inputRef} id="seed-input" maxLength={500} value={input} onChange={event => { setInput(event.target.value); setMessage(''); }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addReference(); } }} placeholder="Paste a DOI, PubMed URL, PMID, or title" aria-describedby="seed-help" /><button type="button" disabled={!pending} aria-label="Add paper reference" onClick={addReference}><Plus size={18} /></button></div>
        {matches.length > 0 && <div className="seed-results" aria-label="Matching sample papers"><span>FROM THE SAMPLE COLLECTION</span>{matches.map(p => <button type="button" key={p.id} onClick={() => { setSeedIds(ids => [...ids, p.id]); setInput(''); setMessage('Starting paper added.'); inputRef.current?.focus(); }}><FileText size={16} /><span><strong>{p.title}</strong><small>{p.authors[0]?.name ?? 'Author unavailable'} · {p.year ?? 'Year unknown'}</small></span><Plus size={16} /></button>)}</div>}
        <div className="seed-selected">{seedIds.map(id => { const paper = papers.find(p => p.id === id)!; return <div className="seed-chip" key={id}><Check size={16} /><span><strong>{paper.title}</strong><small>{paper.year ?? 'Year unknown'} · Sample paper</small></span><button type="button" onClick={() => setSeedIds(ids => ids.filter(value => value !== id))} aria-label={`Remove ${paper.title}`}><X size={15} /></button></div>; })}{references.map(ref => <div className="seed-chip pending-reference" key={ref.toLowerCase()}><FileText size={16} /><span><strong>{ref}</strong><small>Saved reference · Awaiting live lookup</small></span><button type="button" onClick={() => setReferences(refs => refs.filter(value => value !== ref))} aria-label={`Remove ${ref}`}><X size={15} /></button></div>)}</div>
        <p className="seed-help" id="seed-help">External references are saved for future lookup. This demo uses sample papers and does not recalculate scores for your query.</p>
        <p className="research-status" role="status">{message}</p>
        </section>}
      </form>
    </section>
    <p className="search-demo-note">Demo experience · Sample graph and scores · Live discovery isn’t connected yet</p>
  </main>;
}
