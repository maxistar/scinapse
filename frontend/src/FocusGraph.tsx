import useEdgeReasoning from './useEdgeReasoning';
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { Bookmark, Expand, Plus, Minus, X } from 'lucide-react';
import {
  edgeWidth, fitGraphScale, connectionGeometry, focusSubgraph, layoutFocus, relevanceScore,
  scorePalette, FOCUS_NODE_WIDTH, FOCUS_NODE_HEIGHT, type Edge, type FocusTarget, type Paper,
} from './graph';

interface Props {
  papers: Paper[]; edges: Edge[]; target: FocusTarget; types: string[];
  saved: string[]; detailsOpen: boolean; selectedPaperId: string | null;
  onPaper: (id: string) => void; onEdge: (key: string) => void;
  onDetails: (id: string) => void; onClose: () => void;
}

export default function FocusGraph({ papers, edges, target, types, saved, detailsOpen, selectedPaperId, onPaper, onEdge, onDetails, onClose }: Props) {
  const edgeReasoning = useEdgeReasoning();
  const subgraph = useMemo(() => focusSubgraph(papers, edges, target, types), [papers, edges, target, types]);
  const viewport = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; startX: number; startY: number } | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const [size, setSize] = useState({ width: 760, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const availableWidth = size.width;
  const layout = useMemo(() => layoutFocus(subgraph.papers, availableWidth), [subgraph.papers, availableWidth]);
  const targetKey = target.type === 'paper' ? target.id : target.key;
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  useEffect(() => {
    if (!viewport.current) return;
    const observer = new ResizeObserver(entries => { const { width, height } = entries[0].contentRect; setSize({ width, height }); });
    observer.observe(viewport.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => { closeButton.current?.focus({ preventScroll: true }); setSelectedEdge(null); setZoom(1); setPan({ x: 0, y: 0 }); }, [targetKey]);
  useEffect(() => { edgeReasoning.dismiss(); }, [subgraph, zoom, pan]);
  const scale = fitGraphScale(layout.width, layout.height, size.width, size.height) * zoom;
  const worldX = (size.width - layout.width * scale) / 2 + pan.x;
  const worldY = (size.height - layout.height * scale) / 2 + pan.y;

  const activePaperId = selectedPaperId ?? (target.type === 'paper' ? target.id : null);
  const relatedIds = new Set(subgraph.groups.flatMap(group => group.selected.source === activePaperId ? [group.selected.target] : group.selected.target === activePaperId ? [group.selected.source] : []));
  return <>
    {edgeReasoning.tooltip}
    <div className="focus-backdrop" onClick={onClose} aria-hidden="true" />
    <section className={`focus-layer ${detailsOpen ? 'focus-has-details' : ''}`} role="dialog" aria-modal={!detailsOpen} aria-label="Focused research graph" onKeyDown={event => {
      if (event.key !== 'Tab' || detailsOpen) return;
      const buttons = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), [tabindex="0"]')];
      const first = buttons[0]; const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <button ref={closeButton} className="icon-button focus-close" aria-label="Close focus view" title="Back to overview (Esc)" onClick={onClose}><X size={20} /></button>
      <div className="focus-viewport" ref={viewport} aria-label="Focused paper graph, fitted to the window; drag to pan and use zoom controls for larger neighbourhoods" onPointerDown={event => {
        if ((event.target as Element).closest('button, .graph-edge')) return;
        drag.current = { x: event.clientX, y: event.clientY, startX: pan.x, startY: pan.y };
        event.currentTarget.setPointerCapture(event.pointerId);
      }} onPointerMove={event => { if (drag.current) setPan({ x: drag.current.startX + event.clientX - drag.current.x, y: drag.current.startY + event.clientY - drag.current.y }); }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <div className="focus-world" style={{ width: layout.width, height: layout.height, transform: `translate(${worldX}px, ${worldY}px) scale(${scale})` }}>
          <svg className="focus-lines" width={layout.width} height={layout.height} role="group" aria-label="Focused graph connections">
            {layout.years.map(year => <g key={String(year)} className="focus-year"><line x1="75" x2={layout.width - 25} y1={layout.yearY(year)} y2={layout.yearY(year)} /><text x="17" y={layout.yearY(year) + 4}>{year ?? 'Unknown'}</text></g>)}
            {subgraph.groups.map((group, index) => {
              const edge = group.selected;
              const a = layout.positions.get(edge.source)!; const b = layout.positions.get(edge.target)!;
              const geometry = connectionGeometry(a, b, FOCUS_NODE_WIDTH, FOCUS_NODE_HEIGHT, index);
              const path = geometry.path;
              const primary = target.type === 'edge' || edge.source === activePaperId || edge.target === activePaperId;
              return <g key={group.key} className={`graph-edge focus-edge edge-${edge.type} ${primary ? 'focus-primary-edge' : ''} ${selectedEdge === group.key || target.type === 'edge' ? 'edge-active' : ''}`} role="button" tabIndex={0} aria-describedby={edgeReasoning.edgeId === edge.id ? edgeReasoning.id : undefined}
                  onPointerEnter={event => { if (event.pointerType !== 'touch') edgeReasoning.show(edge, event.clientX, event.clientY); }} onPointerLeave={edgeReasoning.hide}
                  onFocus={event => { const bounds = event.currentTarget.getBoundingClientRect(); edgeReasoning.show(edge, bounds.left + bounds.width / 2, bounds.top + bounds.height / 2); }} onBlur={edgeReasoning.hide} aria-label={`Focus connection between ${papers.find(p => p.id === edge.source)?.title} and ${papers.find(p => p.id === edge.target)?.title}`} onClick={() => setSelectedEdge(group.key)} onDoubleClick={() => onEdge(group.key)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedEdge(group.key); } }}>
                <path className="edge-hit" d={path} /><path className="edge-line" d={path} style={{ strokeWidth: edgeWidth(edge) }} />
                {group.all.length > 1 && <g className="edge-count" transform={`translate(${geometry.label.x},${geometry.label.y})`}><rect x="-16" y="-12" width="32" height="24" rx="12" /><text textAnchor="middle" y="4">+{group.all.length - 1}</text></g>}
              </g>;
            })}
          </svg>
          {subgraph.papers.map(paper => {
            const position = layout.positions.get(paper.id)!;
            const score = relevanceScore(paper); const palette = scorePalette(score);
            const isCenter = activePaperId === paper.id;
            const isRelated = relatedIds.has(paper.id);
            return <article className={`focus-paper ${paper.is_seed ? 'focus-seed' : ''} ${isCenter ? 'focus-center' : isRelated ? 'focus-related' : activePaperId ? 'focus-unrelated' : ''}`} key={paper.id} style={{ left: position.x - FOCUS_NODE_WIDTH / 2, top: position.y - FOCUS_NODE_HEIGHT / 2, width: FOCUS_NODE_WIDTH, height: FOCUS_NODE_HEIGHT, '--score-accent': palette.accent, '--score-background': palette.background, '--score-border': palette.border } as CSSProperties}>
              <button className="focus-paper-main" onClick={() => onDetails(paper.id)} onDoubleClick={() => onPaper(paper.id)} aria-label={`Select ${paper.title}`}>
                <span className="focus-paper-meta"><span className="focus-score-dot" style={{ background: score === null ? '#b5bbb1' : palette.accent }} /><span>{paper.year ?? 'Year unknown'}</span>{paper.is_seed && <span className="node-seed-label">Seed</span>}{saved.includes(paper.id) && <Bookmark size={11} fill="currentColor" />}</span>
                <h3>{paper.title}</h3>
              </button>

            </article>;
          })}
        </div>
      </div>
      <div className="focus-zoom"><button aria-label="Zoom out focused graph" title="Zoom out" disabled={zoom <= .5} onClick={() => setZoom(value => Math.max(.5, value - .25))}><Minus size={15} /></button><button aria-label="Zoom in focused graph" title="Zoom in" disabled={zoom >= 4} onClick={() => setZoom(value => Math.min(4, value + .25))}><Plus size={15} /></button><button aria-label="Fit focused graph to window" title="Fit to window" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}><Expand size={14} /></button></div>
    </section>
  </>;
}
