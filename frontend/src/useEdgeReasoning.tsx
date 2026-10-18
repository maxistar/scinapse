import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { relationshipLabel, type Edge } from './graph';

type Preview = { edge: Edge; x: number; y: number };

export default function useEdgeReasoning() {
  const id = useId();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const panel = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  function keep() { clearTimeout(hideTimer.current); }
  function hide() { keep(); hideTimer.current = setTimeout(() => setPreview(null), 140); }
  function show(edge: Edge, x: number, y: number) { keep(); setPreview({ edge, x, y }); }
  function dismiss() { keep(); setPreview(null); }

  useEffect(() => () => clearTimeout(hideTimer.current), []);
  useEffect(() => {
    if (!preview) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopImmediatePropagation(); dismiss(); }
    };
    const scroll = (event: Event) => { if (!(event.target instanceof Node) || !panel.current?.contains(event.target)) dismiss(); };
    window.addEventListener('keydown', escape, true);
    window.addEventListener('resize', dismiss);
    window.addEventListener('scroll', scroll, true);
    return () => {
      window.removeEventListener('keydown', escape, true);
      window.removeEventListener('resize', dismiss);
      window.removeEventListener('scroll', scroll, true);
    };
  }, [preview]);
  useLayoutEffect(() => {
    if (!preview || !panel.current) return;
    const { width, height } = panel.current.getBoundingClientRect();
    const left = Math.max(12, Math.min(preview.x + 16, window.innerWidth - width - 12));
    const top = preview.y + 18 + height <= window.innerHeight - 12 ? preview.y + 18 : Math.max(12, preview.y - height - 14);
    setPosition({ left, top });
  }, [preview]);

  const tooltip = preview && createPortal(<div ref={panel} id={id} role="tooltip" className="edge-reasoning-tooltip" style={position} onPointerEnter={keep} onPointerLeave={hide}>
    <span>{relationshipLabel(preview.edge.type)}</span>
    <p>{preview.edge.reasoning.summary || 'No reasoning is available for this connection.'}</p>
  </div>, document.body);

  return { id, edgeId: preview?.edge.id, show, hide, dismiss, tooltip };
}
