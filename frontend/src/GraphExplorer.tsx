import useEdgeReasoning from './useEdgeReasoning';
import { useEffect, useMemo, useRef, useState, createContext, useContext, type CSSProperties } from 'react';
import {
  ArrowUpRight, Bookmark, Check, ChevronDown, ChevronRight,
  CircleHelp, Compass, Download, Expand, ExternalLink, FileText,
  GitBranch, Link2, Minus, Network, Plus, Search, ShieldCheck,
  SlidersHorizontal, Sparkles, X, MoreHorizontal, RotateCcw, AlertTriangle, History,
} from 'lucide-react';
import FocusGraph from './FocusGraph';
import type { ResearchSession } from './research';
import { groupEdges, layoutPapers, connectionGeometry, pairKey, relationshipLabel, relationshipDescriptions, evidenceDescription, passesRelevance, type Edge, type GraphData, type FocusTarget, edgeWidth, qualityScore, relevanceScore, scorePalette, NODE_WIDTH, NODE_HEIGHT } from './graph';

const format = (text: string) => text.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const scoreLabel = (score: number | null) => score === null ? 'Unknown' : `${Math.round(score * 100)}`;

function readSaved(data: GraphData): string[] {
  const savedStorageKey = `scinapse-saved:${data.exploration_id}`;
  try {
    const stored = localStorage.getItem(savedStorageKey);
    const parsed = stored ? JSON.parse(stored) : null;
    if (Array.isArray(parsed) && parsed.every(id => typeof id === 'string')) return parsed;
  } catch { /* The explorer remains usable when browser storage is unavailable. */ }
  return data.nodes.filter(p => p.review.saved).map(p => p.id);
}

const GraphContext = createContext<GraphData | null>(null);
interface ExplorerProps { data: GraphData; research: ResearchSession | null; onNewSearch: () => void; onHistory: () => void }
export default function GraphExplorer(props: ExplorerProps) {
  return <GraphContext.Provider value={props.data}><Explorer {...props} /></GraphContext.Provider>;
}
function Explorer({ data, research, onNewSearch, onHistory }: ExplorerProps) {
  const allTypes = useMemo(() => [...new Set(data.edges.map(edge => edge.type))], [data.edges]);
  const savedStorageKey = `scinapse-saved:${data.exploration_id}`;
  const seedIds = data.nodes.filter(p => p.is_seed).map(p => p.id);
  const hasRelevanceScores = data.nodes.some(p => relevanceScore(p) !== null);
  const paperById = (id: string) => data.nodes.find(p => p.id === id)!;

  const edgeReasoning = useEdgeReasoning();
  const [selection, setSelection] = useState<string | null>(null);
  const [focusTarget, setFocusTarget] = useState<FocusTarget | null>(null);
  const [selectedPair, setSelectedPair] = useState<string | null>(null);
  const [tab, setTab] = useState('Overview');
  const [section, setSection] = useState('explore');
  const [search, setSearch] = useState('');
  const [types, setTypes] = useState(allTypes);
  const [minRelevance, setMinRelevance] = useState(0);
  const [showFilters, setShowFilters] = useState(false);
  const [help, setHelp] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [showNotices, setShowNotices] = useState(false);
  const [saved, setSaved] = useState<string[]>(() => readSaved(data));
  const [storageWarning, setStorageWarning] = useState(false);
  const [revealed, setRevealed] = useState(data.nodes.map(p => p.id));
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const [canvasWidth, setCanvasWidth] = useState(800);
  useEffect(() => {
    if (!svgRef.current) return;
    const observer = new ResizeObserver(entries => setCanvasWidth(entries[0].contentRect.width));
    observer.observe(svgRef.current);
    return () => observer.disconnect();
  }, []);
  const drag = useRef<{ x: number; y: number; startX: number; startY: number } | null>(null);

  const selected = paperById(selection ?? data.nodes[0].id);
  const inspectorOpen = selection !== null;
  const visible = useMemo(() => data.nodes.filter(p =>
    revealed.includes(p.id) && passesRelevance(p, minRelevance) &&
    (section !== 'saved' || saved.includes(p.id)) &&
    (section !== 'collection' || p.is_seed) &&
    (!search || `${p.title} ${p.topics.join(' ')} ${p.methods.join(' ')} ${p.authors.map(a => a.name).join(' ')}`.toLowerCase().includes(search.toLowerCase()))
  ), [data.nodes, revealed, minRelevance, section, saved, search]);
  useEffect(() => { edgeReasoning.dismiss(); }, [visible, types, view]);
  const visibleIds = new Set(visible.map(p => p.id));
  const groups = groupEdges(data.edges, types).filter(g => visibleIds.has(g.selected.source) && visibleIds.has(g.selected.target));
  const activePaperId = selection ?? (focusTarget?.type === 'paper' ? focusTarget.id : null);
  const relatedIds = new Set(groups.flatMap(group => group.selected.source === activePaperId ? [group.selected.target] : group.selected.target === activePaperId ? [group.selected.source] : []));
  const layout = layoutPapers(visible, data.nodes);
  const connected = data.edges.filter(e => e.source === selection || e.target === selection);
  const neighbours = [...new Set(connected.map(e => e.source === selection ? e.target : e.source))];
  const hiddenNeighbours = neighbours.filter(id => !revealed.includes(id));
  const width = (canvasWidth < 600 ? 600 : layout.width) / view.zoom;
  const height = layout.height / view.zoom;
  const viewLeft = (layout.width - width) / 2 - view.x;
  const yearLabelX = Math.max(38, viewLeft + 12);
  const viewBox = `${viewLeft} ${(layout.height - height) / 2 - view.y} ${width} ${height}`;

  function closeInspector() { setSelection(null); }
  function closeFocus() { edgeReasoning.dismiss(); setFocusTarget(null); setSelection(null); setSelectedPair(null); }
  function selectEdge(key: string) { setSelection(null); setSelectedPair(key); }
  function openEdgeFocus(key: string) { edgeReasoning.dismiss(); setFocusTarget({ type: 'edge', key }); setSelection(null); setSelectedPair(key); }
  function openPaperFocus(id: string) { edgeReasoning.dismiss(); setFocusTarget({ type: 'paper', id }); setSelection(null); setSelectedPair(null); }
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { closeFocus(); setHelp(false); setShowMenu(false); setShowFilters(false); setShowNotices(false); }
    };
    const onClick = (event: PointerEvent) => { if (!(event.target as Element).closest('.more-menu')) setShowMenu(false); };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onClick);
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('pointerdown', onClick); };
  }, []);

  function selectPaper(id: string) { setSelection(id); setSelectedPair(null); setTab('Overview'); }
  function toggleSave(id: string) {
    const next = saved.includes(id) ? saved.filter(x => x !== id) : [...saved, id];
    setSaved(next);
    try { localStorage.setItem(savedStorageKey, JSON.stringify(next)); } catch { setStorageWarning(true); }
  }
  function reset() {
    edgeReasoning.dismiss(); setSearch(''); setMinRelevance(0); setTypes(allTypes); setRevealed(data.nodes.map(p => p.id));
    setFocusTarget(null); setView({ zoom: 1, x: 0, y: 0 }); setSection('explore'); setSelectedPair(null); setSelection(null); setTab('Overview'); setShowFilters(false); setShowMenu(false); setShowNotices(false);
  }
  function exportGraph() {
    const result = { ...data, input: research, nodes: data.nodes.filter(p => visibleIds.has(p.id)).map(p => ({ ...p, review: { ...p.review, saved: saved.includes(p.id) } })), edges: data.edges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target) && types.includes(e.type)) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'scinapse-exploration.json'; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="app-shell">
    {edgeReasoning.tooltip}
    <main className="main">
      <div className={`explorer-layout ${inspectorOpen ? 'has-inspector' : ''} ${focusTarget ? 'is-focused' : ''}`}>
        <section className="graph-panel" aria-label="Publication timeline explorer" inert={focusTarget !== null}>
          <header className="graph-toolbar">
            <a className="compact-brand" href="/" onClick={e => { e.preventDefault(); reset(); onNewSearch(); }} aria-label="Start a new research search"><Network size={20} /><span>scinapse<span>.</span></span></a>
            <div className="research-context" title={data.research_question}><span>{data.research_question}</span><small>{seedIds.length} seed{seedIds.length === 1 ? '' : 's'}</small></div>
            <div className="toolbar-actions"><label className="search"><Search size={16} /><input aria-label="Search papers" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search papers" />{search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={13} /></button>}</label><button className={`filter-button ${showFilters ? 'selected' : ''}`} onClick={() => setShowFilters(!showFilters)} aria-label="Toggle graph filters" aria-expanded={showFilters}><SlidersHorizontal size={17} />{(types.length !== allTypes.length || minRelevance > 0 || section !== 'explore') && <i />}</button>
            <div className="more-menu"><button className="icon-button" aria-label="More options" aria-expanded={showMenu} aria-haspopup="menu" onClick={() => setShowMenu(!showMenu)}><MoreHorizontal size={21} /></button>{showMenu && <div className="options-menu" role="menu"><button role="menuitem" onClick={() => { onHistory(); setShowMenu(false); }}><History size={15} />Research history</button><button role="menuitem" onClick={() => { exportGraph(); setShowMenu(false); }}><Download size={15} /> Export graph</button><button role="menuitem" onClick={reset}><RotateCcw size={15} /> Reset exploration</button><button role="menuitem" onClick={() => { setHelp(true); setShowMenu(false); }}><CircleHelp size={15} /> How to explore</button><p>{data.is_demo ? 'Demo graph' : 'Generated graph'} · {data.nodes.length} papers</p></div>}</div></div>
          </header>
          {showFilters && <div className="filters"><div className="collection-filter" role="group" aria-label="Paper collection">{[['explore', 'All papers'], ['collection', 'Starting papers'], ['saved', 'Saved papers']].map(([value,label]) => <button key={value} className={section === value ? 'collection-active' : ''} aria-pressed={section === value} onClick={() => setSection(value)}>{label}{value === 'saved' && <span>{saved.length}</span>}</button>)}</div><div className="relevance-filter"><label htmlFor="relevance-filter">Minimum relevance <strong>{!hasRelevanceScores ? 'Unassessed' : minRelevance === 0 ? 'Any' : `${minRelevance} / 100`}</strong></label><input id="relevance-filter" disabled={!hasRelevanceScores} aria-describedby="relevance-filter-help" type="range" min="0" max="100" step="5" value={minRelevance} aria-valuetext={!hasRelevanceScores ? 'Relevance unassessed' : minRelevance === 0 ? 'Any relevance, including unassessed' : `${minRelevance} out of 100 minimum`} onChange={e => setMinRelevance(Number(e.target.value))} /><p id="relevance-filter-help">{!hasRelevanceScores ? 'No relevance scores were returned. Run a search with assessments enabled.' : minRelevance === 0 ? 'Includes papers with unassessed relevance.' : 'Seed papers always stay visible. Other unassessed papers are hidden.'}</p></div><fieldset><legend>Relationship types</legend>{allTypes.map(type => <label key={type} title={relationshipDescriptions[type]}><input type="checkbox" checked={types.includes(type)} onChange={() => setTypes(types.includes(type) ? types.filter(t => t !== type) : [...types, type])} />{relationshipLabel(type)}</label>)}</fieldset><button className="text-button" onClick={reset}>Reset</button></div>}
          <div className="canvas-wrap">
            {showNotices && <section className="graph-notices" aria-label="Graph notices"><div className="notices-heading"><strong>Retrieval notices</strong><button className="icon-button" aria-label="Close graph notices" onClick={() => setShowNotices(false)}><X size={16} /></button></div><ul>{data.warnings.map((warning, index) => { const paper = data.nodes.find(p => p.id === warning.node_id); return <li key={`${warning.code}-${index}`}><strong>{format(warning.code)}</strong><p>{warning.message}</p>{paper ? <button onClick={() => { selectPaper(paper.id); setShowNotices(false); }}>{paper.title}<ArrowUpRight size={12} /></button> : warning.node_id && <small>{warning.node_id}</small>}</li>; })}</ul></section>}

            <svg ref={svgRef} className="graph-svg" viewBox={viewBox} role="group" aria-label="Paper graph arranged by publication year. Select a paper or relationship to inspect its evidence."
              onPointerDown={e => { if ((e.target as Element).closest('[data-interactive]')) return; drag.current = { x: e.clientX, y: e.clientY, startX: view.x, startY: view.y }; e.currentTarget.setPointerCapture(e.pointerId); }}
              onPointerMove={e => { if (!drag.current || !svgRef.current) return; const ratio = Math.max(width / svgRef.current.clientWidth, height / svgRef.current.clientHeight); setView(v => ({ ...v, x: drag.current!.startX + (e.clientX - drag.current!.x) * ratio, y: drag.current!.startY + (e.clientY - drag.current!.y) * ratio })); }}
              onPointerUp={e => { if (drag.current && Math.abs(e.clientX - drag.current.x) < 4 && Math.abs(e.clientY - drag.current.y) < 4) closeInspector(); drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
              <defs><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.7" fill="#d6d9d2" /></pattern></defs>
              <rect x="-3000" y="-3000" width="9000" height="9000" fill="url(#dots)" />
              {layout.years.map(year => <g key={year} className="year-band"><line x1={yearLabelX + 67} y1={layout.yearY(year)} x2={layout.width - 40} y2={layout.yearY(year)} /><text x={yearLabelX} y={layout.yearY(year) + 5}>{year}</text>{year === layout.years[0] && <text x={yearLabelX} y={layout.yearY(year) - 23} className="year-new">LATEST</text>}</g>)}
              {data.nodes.some(p => p.year === null) && <text className="year-unknown" x="25" y={layout.yearY(null)}>Year unknown</text>}
              {groups.map((group, edgeIndex) => {
                const edge = group.selected;
                const a = layout.positions.get(edge.source)!; const b = layout.positions.get(edge.target)!;
                const geometry = connectionGeometry(a, b, NODE_WIDTH, NODE_HEIGHT, edgeIndex);
                const curve = geometry.path;
                const active = selectedPair ? selectedPair === group.key : edge.source === activePaperId || edge.target === activePaperId;
                const { x: midX, y: midY } = geometry.label;
                return <g key={group.key} data-interactive="true" className={`graph-edge ${active ? 'edge-active' : activePaperId ? 'edge-muted' : ''} edge-${edge.type}`} role="button" tabIndex={0} aria-describedby={edgeReasoning.edgeId === edge.id ? edgeReasoning.id : undefined}
                  onPointerEnter={event => { if (event.pointerType !== 'touch') edgeReasoning.show(edge, event.clientX, event.clientY); }} onPointerLeave={edgeReasoning.hide}
                  onFocus={event => { const bounds = event.currentTarget.getBoundingClientRect(); edgeReasoning.show(edge, bounds.left + bounds.width / 2, bounds.top + bounds.height / 2); }} onBlur={edgeReasoning.hide} aria-pressed={selectedPair === group.key} aria-label={`${relationshipLabel(edge.type)} between ${paperById(edge.source).title} and ${paperById(edge.target).title}; ${group.all.length} relationships`} onClick={() => { selectEdge(group.key); }} onDoubleClick={() => openEdgeFocus(group.key)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectEdge(group.key); } }}>
                  <path className="edge-hit" d={curve} /><path className="edge-line" d={curve} style={{ strokeWidth: edgeWidth(edge) }} />
                  {group.all.length > 1 && <g className="edge-count" transform={`translate(${midX},${midY})`}><rect x="-16" y="-12" width="32" height="24" rx="12" /><text textAnchor="middle" y="4">+{group.all.length - 1}</text></g>}
                </g>;
              })}
              {visible.map(p => {
                const pos = layout.positions.get(p.id)!;
                const isSelected = activePaperId === p.id;
                const isRelated = relatedIds.has(p.id);
                const relevance = relevanceScore(p);
                const palette = scorePalette(relevance);
                const nodeStyle = { '--score-accent': palette.accent, '--score-background': palette.background, '--score-border': palette.border } as CSSProperties;
                return <foreignObject data-interactive="true" key={p.id} x={pos.x - NODE_WIDTH / 2} y={pos.y - NODE_HEIGHT / 2} width={NODE_WIDTH} height={NODE_HEIGHT + 4}>
                  <button style={nodeStyle} className={`paper-node ${p.is_seed ? 'seed-node' : ''} ${isSelected ? 'node-selected' : isRelated ? 'node-related' : activePaperId ? 'node-muted' : ''} ${relevance === null ? 'score-unknown' : 'score-assessed'}`} aria-pressed={isSelected} onClick={() => selectPaper(p.id)} onDoubleClick={() => openPaperFocus(p.id)} title={`${p.title} · Relevance: ${relevance === null ? 'unassessed' : `${Math.round(relevance * 100)}/100`}`} aria-label={`${p.title}, ${p.year ?? 'year unknown'}, ${p.is_seed ? 'starting paper' : 'discovered paper'}, relevance ${scoreLabel(p.relevance.score)}`}>
                    <span className="node-score-dot" aria-label={relevance === null ? 'Relevance unassessed' : `Relevance ${Math.round(relevance * 100)} out of 100`} />
                    <span className="node-content"><strong>{p.title}</strong><span className="node-meta"><span>{p.year ?? 'Unknown year'}</span>{p.is_seed && <span className="node-seed-label">Seed</span>}<span className="node-relevance" title="Relevance to your research question">{p.relevance.score === null ? 'Relevance —' : `${scoreLabel(p.relevance.score)} relevance`}</span>{saved.includes(p.id) && <Bookmark size={10} fill="currentColor" />}</span></span>
                  </button>
                </foreignObject>;
              })}
            </svg>
            {(selection || selectedPair) && !focusTarget && <button className="selection-focus-button" onClick={() => selectedPair ? openEdgeFocus(selectedPair) : selection && openPaperFocus(selection)} title="Open focus view. You can also double-click a paper or connection."><Expand size={14} />Focus selection</button>}
            {visible.length === 0 && <div className="empty-state"><Search size={27} /><h3>No papers in this view</h3><p>Try another search or reset your filters.</p><button className="button primary" onClick={reset}>Reset explorer</button></div>}
            <div className="canvas-bottom"><div className="canvas-context"><button className="legend-toggle" aria-expanded={showLegend} onClick={() => setShowLegend(!showLegend)}><CircleHelp size={14} /> Legend</button><span className="canvas-count">{visible.length} papers <span>·</span> {data.is_demo ? 'Demo graph' : 'Generated graph'}</span>{data.warnings.length > 0 && <button className="notices-toggle" aria-expanded={showNotices} onClick={() => setShowNotices(open => !open)}><AlertTriangle size={13} />{data.warnings.length} notices</button>}{showLegend && <div className="graph-legend"><div className="legend-section"><span><i className="legend-seed" /> Seed paper</span><span><i className="legend-candidate" /> Relevance unassessed</span></div><div className="relevance-scale"><strong>Relevance to your question</strong><div className="relevance-gradient" /><div className="relevance-scale-labels"><span>Lower</span><span>Higher</span></div><p>Red means lower relevance; green means higher relevance. Gray is unassessed. Blue identifies seeds; their dot shows relevance.</p></div><div className="legend-section">{allTypes.map(type => <span key={type} title={relationshipDescriptions[type]}><i className={`legend-relationship legend-${type}`} />{relationshipLabel(type)}</span>)}</div><p className="legend-explanation">Citation overlap can represent a direct citation or shared references.</p><div className="strength-legend"><span>Connection strength</span><div><i /><i /><i /></div><p>Line width follows display score: a higher score means a thicker line.</p></div></div>}</div><div className="zoom-controls"><button aria-label="Zoom out" disabled={view.zoom <= .6} onClick={() => setView(v => ({ ...v, zoom: Math.max(.6, v.zoom - .2) }))}><Minus size={15} /></button><span>{Math.round(view.zoom * 100)}%</span><button aria-label="Zoom in" disabled={view.zoom >= 2.4} onClick={() => setView(v => ({ ...v, zoom: Math.min(2.4, v.zoom + .2) }))}><Plus size={15} /></button><span className="control-divider" /><button aria-label="Fit graph to view" onClick={() => setView({ zoom: 1, x: 0, y: 0 })}><Expand size={15} /></button></div></div>
          </div>
        </section>

        {focusTarget && <FocusGraph papers={visible} edges={data.edges} target={focusTarget} types={types} saved={saved} detailsOpen={inspectorOpen} selectedPaperId={selection} onPaper={openPaperFocus} onEdge={openEdgeFocus} onDetails={id => { setSelection(id); setTab('Overview'); }} onClose={closeFocus} />}

        {inspectorOpen && <aside className="inspector" aria-label="Paper details">
            <div className="inspector-top"><span>Paper</span><div className="inspector-tools"><button className="icon-button" aria-label="Open focused graph" title="Focus on this paper" onClick={() => openPaperFocus(selected.id)}><Expand size={16} /></button><button className="icon-button" aria-label="Close details" onClick={closeInspector}><X size={18} /></button></div></div>
            <div className="paper-heading"><div className="paper-meta"><span>{selected.year}</span><i /><span>{selected.publication_status.type === 'preprint' ? 'Preprint' : 'Research paper'}</span>{selected.is_seed && <span className="seed-label">Starting paper</span>}</div><h2>{selected.title}</h2>{selected.authors.length > 2 ? <details className="paper-authors" key={selected.id}><summary><span>{selected.authors.slice(0, 2).map(a => a.name).join(', ')}</span><span className="author-toggle"><span className="authors-expand">+{selected.authors.length - 2} more</span><span className="authors-collapse">Show less</span><ChevronDown size={12} /></span></summary><p className="authors authors-full">{selected.authors.map(a => a.name).join(', ')}</p></details> : <p className="authors">{selected.authors.map(a => a.name).join(', ') || 'Authors unavailable'}</p>}<p className="journal">{selected.journal ?? 'Journal unavailable'}</p><div className="paper-actions"><a className="button secondary" href={selected.url} target="_blank" rel="noreferrer">View source<ExternalLink size={13} /></a><button className={`button ${saved.includes(selected.id) ? 'saved-button' : 'primary'}`} onClick={() => toggleSave(selected.id)}>{saved.includes(selected.id) ? <Check size={14} /> : <Bookmark size={14} />}{saved.includes(selected.id) ? 'Saved' : 'Save paper'}</button></div></div>
            <div className="detail-tabs" role="tablist" aria-label="Paper information">{['Overview', 'Connections', 'Quality'].map(t => <button key={t} role="tab" aria-selected={tab === t} id={`tab-${t}`} aria-controls="paper-tabpanel" className={tab === t ? 'tab-active' : ''} onClick={() => setTab(t)}>{t}{t === 'Connections' && <span>{neighbours.length}</span>}</button>)}</div>
            <div className="inspector-body" role="tabpanel" id="paper-tabpanel" aria-labelledby={`tab-${tab}`}>
              {tab === 'Overview' && <><div className="relevance-card"><div className="section-title"><span><Sparkles size={14} /> RELEVANCE TO YOUR QUESTION</span><CircleHelp size={13} aria-label="Relevance is question alignment, not a probability or research quality score" /></div><div className="relevance-value">{scoreLabel(selected.relevance.score)}{selected.relevance.score !== null && <span>/ 100</span>}<span className="assessment-pill">{format(selected.relevance.assessment)}</span></div><div className="score-track"><div style={{ width: `${(selected.relevance.score ?? 0) * 100}%` }} /></div><p>{selected.relevance.reason}</p></div>
              <div className="detail-section"><h3><span className="section-icon"><FileText size={14} /></span>Supporting evidence<span className="small-label">ABSTRACT</span></h3>{selected.relevance.supporting_evidence_ids.map(id => <EvidenceQuote key={id} id={id} />)}{!selected.abstract_available && <div className="notice amber">No abstract available. Relevance remains uncertain.</div>}</div>
              <div className="detail-section"><h3><span className="uncertainty-dot" /> What remains uncertain</h3><ul className="uncertainty-list">{selected.relevance.uncertainties.map(u => <li key={u}>{u}</li>)}</ul></div>
              <div className="detail-section"><h3>Research signals</h3><div className="topic-tags">{[...selected.topics, ...selected.methods].map(t => <button key={t} onClick={() => setSearch(t)}>{t}</button>)}</div></div>
              <details className="abstract-details"><summary>Read full abstract<ChevronDown size={14} /></summary><p>{selected.abstract?.text ?? 'No abstract was retrieved for this paper.'}</p></details></>}
              {tab === 'Connections' && <><div className="section-title"><span>CONNECTED PAPERS</span><span>{neighbours.length}</span></div><p className="muted">Select a connection to highlight it on the graph.</p>{neighbours.map(id => { const edges = connected.filter(e => e.source === id || e.target === id); const p = paperById(id); return <div className="connection-group" key={id}><button className="connection-item" onClick={() => selectEdge(pairKey(edges[0]))}><span className="connection-icon"><Link2 size={16} /></span><div><strong>{p.title}</strong><small>{p.year} · {edges.length} relationship{edges.length !== 1 ? 's' : ''}</small><span>{[...new Set(edges.map(e => relationshipLabel(e.type)))].join(' · ')}</span></div><ChevronRight size={15} /></button><details className="abstract-details"><summary>Relationship evidence<ChevronDown size={14} /></summary>{edges.map(edge => <RelationshipCard key={edge.id} edge={edge} primary={false} />)}</details></div>; })}<div className="notice">The graph shows the highest display score per pair. Hover over a line for its explanation.</div></>}
              {tab === 'Quality' && <><div className="quality-intro"><ShieldCheck size={22} /><h3>Paper quality</h3><div className="paper-quality-score" style={{ color: scorePalette(qualityScore(selected)).accent }}>{qualityScore(selected) === null ? 'Unassessed' : `${Math.round(qualityScore(selected)! * 100)} / 100`}</div><p>{selected.research_assessment.summary}</p><span className="small-label">{format(selected.research_assessment.status)} assessment</span></div>{Object.entries(selected.research_assessment.dimensions).map(([key, value]) => <div className="quality-dimension" key={key}><div><h4>{format(key)}</h4><span>{format(value.assessment)}</span></div><p>{value.reason}</p>{value.evidence_ids.map(id => <EvidenceQuote key={id} id={id} />)}</div>)}<div className="detail-section"><h3>Publication checks</h3>{Object.entries(selected.publication_status).map(([key,value]) => <div className="metadata-row" key={key}><span>{format(key)}</span><strong>{format(value)}</strong></div>)}</div><p className="muted">Assessed from: {selected.research_assessment.evaluated_from.join(', ')}.</p>{selected.research_assessment.limitations.map(l => <p className="muted" key={l}>{l}</p>)}</>}
            </div>
            <div className="inspector-bottom">{hiddenNeighbours.length > 0 && <button className="button secondary expand-button" onClick={() => { setRevealed(ids => [...new Set([...ids, ...hiddenNeighbours])]); setSection('explore'); setSearch(''); setMinRelevance(0); }}><GitBranch size={15} />{hiddenNeighbours.length ? `Reveal ${hiddenNeighbours.length} connected papers` : `All ${neighbours.length} connections shown`}</button>}{!selected.is_seed && <button className="text-button hide-paper" onClick={() => { setRevealed(ids => ids.filter(id => id !== selection)); closeFocus(); }}>Hide this paper from graph</button>}</div>
        </aside>}
      </div>
      {storageWarning && <div className="storage-toast" role="status">Saved for this session. Browser storage is unavailable.<button onClick={() => setStorageWarning(false)} aria-label="Dismiss storage notice"><X size={14} /></button></div>}
    </main>
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="guide-modal" role="dialog" aria-modal="true" aria-labelledby="guide-title" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape') setHelp(false); }}><button autoFocus className="icon-button modal-close" onClick={() => setHelp(false)} aria-label="Close guide"><X size={20} /></button><span className="guide-icon"><Compass size={28} /></span><div className="eyebrow">A LITTLE ORIENTATION</div><h2 id="guide-title">Follow your curiosity.</h2><p>Start with the blue seed papers. Follow their connections to discover related work across the timeline.</p><ol><li><strong>Read the colors.</strong> Seed papers are blue. Question relevance runs from red through amber to green. Gray means relevance is unassessed; line thickness follows the relationship display score.</li><li><strong>Read the timeline.</strong> Newest papers sit at the top; empty years preserve the passage of time.</li><li><strong>Inspect a paper.</strong> Select a paper to inspect it. Use Focus selection or double-click a paper to bring its neighbourhood forward. Icon controls provide paper information and focus navigation.</li><li><strong>Follow a connection.</strong> Select a line or + badge to highlight it. Use Focus selection or double-click to bring its two papers forward. Escape returns to the overview.</li><li><strong>Build your shortlist.</strong> Save papers to revisit them. Search and filters help narrow the graph.</li></ol><div className="notice">This view shows a graph produced by the backend. Missing scores remain unassessed; retrieval notices describe incomplete results.</div><button className="button primary" onClick={() => setHelp(false)}>Start exploring<ArrowUpRight size={15} /></button></section></div>}
  </div>;
}

function EvidenceQuote({ id }: { id: string }) {
  const data = useContext(GraphContext)!;
  const evidence = data.evidence.find(e => e.id === id);
  if (!evidence) return null;
  return <blockquote className="evidence-quote"><p>{evidenceDescription(evidence, data.nodes)}</p><footer><span>{format(evidence.source_field ?? evidence.type)} · {format(evidence.provenance)}</span>{evidence.source_url && <a href={evidence.source_url} target="_blank" rel="noreferrer" aria-label="Open evidence source"><ArrowUpRight size={14} /></a>}</footer></blockquote>;
}

function RelationshipCard({ edge, primary }: { edge: Edge; primary: boolean }) {
  return <article className="relationship-card">
    <div className="relationship-header"><span><Link2 size={14} />{relationshipLabel(edge.type)}</span>{primary && <span className="small-label">SHOWN ON GRAPH</span>}</div>
    <p>{edge.reasoning.summary}</p>
    {edge.strength.value !== null && <div className="connection-strength"><span>Connection strength</span><strong>{edge.strength.value.toFixed(2)}</strong></div>}
    {edge.reasoning.supporting_evidence_ids.map(id => <EvidenceQuote key={id} id={id} />)}
    <details className="abstract-details"><summary>How this was assessed<ChevronDown size={14} /></summary>
      <p>{edge.strength.explanation}</p>
      <div className="metadata-row"><span>Metric</span><strong>{format(edge.strength.metric)}</strong></div>
      <div className="metadata-row"><span>Display priority</span><strong>{edge.display_score.value?.toFixed(2) ?? 'Unknown'}</strong></div>
      <div className="relation-direction">{edge.directed ? `${edge.source} → ${edge.target}` : 'Undirected relationship'}</div>
      <div className="verification-label"><ShieldCheck size={13} />{format(edge.verification.status)} · {edge.verification.provider}</div>
      <p>Confidence: {format(edge.confidence.level)}. {edge.confidence.reason}</p>
      {edge.reasoning.limitations.map(l => <p key={l}>{l}</p>)}
    </details>
  </article>;
}
