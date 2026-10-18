export interface Evidence {
  id: string; type: string; paper_id: string; quote?: string; source_field?: string;
  source_url: string | null; provenance: string; referenced_paper_ids?: string[];
}
export interface Assessment {
  assessment: string; reason: string; evidence_ids: string[];
}
export interface Paper {
  id: string; title: string; year: number | null; is_seed: boolean; url: string;
  authors: { name: string }[]; institutions: { name: string }[];
  journal: string | null; abstract_available: boolean;
  abstract: { text: string; source_url: string } | null;
  topics: string[]; methods: string[];
  publication_status: { type: string; peer_review: string; correction_status: string; retraction_status: string };
  relevance: { score: number | null; status: string; assessment: string; reason: string; supporting_evidence_ids: string[]; uncertainties: string[]; dimensions: Record<string, number | null> };
  research_assessment: { status: string; overall_score: number | null; summary: string; dimensions: Record<string, Assessment>; evaluated_from: string[]; limitations: string[] };
  review: { saved: boolean; decision: string | null; note: string | null };
}
export interface Edge {
  id: string; source: string; target: string; type: string; directed: boolean;
  reasoning: { summary: string; supporting_evidence_ids: string[]; limitations: string[]; shared_topics?: string[]; shared_methods?: string[] };
  strength: { value: number | null; metric: string; explanation: string; range?: [number, number] };
  confidence: { level: string; reason: string };
  verification: { status: string; provider: string; source_url: string | null; evidence_ids: string[] };
  display_score: { value: number | null; method: string };
}
export interface GraphData {
  research_question: string; is_demo: boolean; nodes: Paper[]; edges: Edge[]; evidence: Evidence[];
  next_cursor: string | null;
}
export const relationshipLabels: Record<string, string> = {
  cites: 'Citations', similar_to: 'Semantic similarity', shared_references: 'Shared references',
};
export const NODE_WIDTH = 224;
export const NODE_HEIGHT = 72;

export function connectionGeometry(a: { x: number; y: number }, b: { x: number; y: number }, width: number, height: number, index = 0) {
  const sameRow = a.y === b.y;
  const longEdge = Math.abs(a.y - b.y) > Math.max(height * 2, 200);
  if (sameRow) {
    const direction = b.x > a.x ? 1 : -1;
    const start = { x: a.x + direction * width / 2, y: a.y };
    const end = { x: b.x - direction * width / 2, y: b.y };
    const middle = (start.x + end.x) / 2;
    return { start, end, path: `M ${start.x} ${start.y} C ${middle} ${start.y}, ${middle} ${end.y}, ${end.x} ${end.y}`, label: { x: middle, y: a.y } };
  }
  if (longEdge) {
    const side = index % 2 === 0 ? -1 : 1;
    const start = { x: a.x + side * width / 2, y: a.y };
    const end = { x: b.x + side * width / 2, y: b.y };
    const laneX = side < 0 ? Math.min(a.x, b.x) - width * .95 : Math.max(a.x, b.x) + width * .95;
    return { start, end, path: `M ${start.x} ${start.y} C ${laneX} ${start.y}, ${laneX} ${end.y}, ${end.x} ${end.y}`, label: { x: (start.x + end.x) / 8 + laneX * .75, y: (a.y + b.y) / 2 } };
  }
  const direction = b.y > a.y ? 1 : -1;
  const start = { x: a.x, y: a.y + direction * height / 2 };
  const end = { x: b.x, y: b.y - direction * height / 2 };
  const middle = (start.y + end.y) / 2;
  return { start, end, path: `M ${start.x} ${start.y} C ${start.x} ${middle}, ${end.x} ${middle}, ${end.x} ${end.y}`, label: { x: (a.x + b.x) / 2, y: middle } };
}

export function edgeWidth(edge: Edge): number {
  const score = edge.display_score.value;
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1 ? 1 + score * 4.5 : 1.2;
}

export function qualityScore(paper: Paper): number | null {
  const score = paper.research_assessment.overall_score;
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1 ? score : null;
}

export function relevanceScore(paper: Paper): number | null {
  const score = paper.relevance.score;
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1 ? score : null;
}

export function scorePalette(score: number | null) {
  if (score === null || !Number.isFinite(score) || score < 0 || score > 1) {
    return { accent: '#9aa09e', background: '#ffffff', border: '#d6d9d4' };
  }
  const stops = [[197, 85, 75], [194, 148, 49], [45, 137, 93]];
  const index = score < .5 ? 0 : 1;
  const t = score < .5 ? score * 2 : (score - .5) * 2;
  const color = stops[index].map((v, i) => Math.round(v + (stops[index + 1][i] - v) * t));
  const mixWithWhite = (opacity: number) => `rgb(${color.map(c => Math.round(255 * (1 - opacity) + c * opacity)).join(', ')})`;
  return { accent: `rgb(${color.join(', ')})`, background: mixWithWhite(.10), border: mixWithWhite(.48) };
}
export function pairKey(edge: Pick<Edge, 'source' | 'target'>) {
  return [edge.source, edge.target].sort().join('::');
}
export function groupEdges(edges: Edge[], enabledTypes: string[]) {
  const groups = new Map<string, Edge[]>();
  for (const edge of edges) {
    if (!enabledTypes.includes(edge.type)) continue;
    const key = pairKey(edge);
    groups.set(key, [...(groups.get(key) ?? []), edge]);
  }
  return [...groups.entries()].flatMap(([key, all]) => {
    const ranked = all.filter(e => e.display_score.value !== null).sort((a, b) =>
      (b.display_score.value! - a.display_score.value!) || a.id.localeCompare(b.id));
    return ranked.length ? [{ key, selected: ranked[0], all }] : [];
  });
}

export type FocusTarget = { type: 'paper'; id: string } | { type: 'edge'; key: string };

export function focusSubgraph(papers: Paper[], edges: Edge[], target: FocusTarget, types: string[]) {
  const available = new Set(papers.map(p => p.id));
  const groups = groupEdges(edges, types).filter(g => available.has(g.selected.source) && available.has(g.selected.target));
  const ids = new Set<string>();
  if (target.type === 'paper' && available.has(target.id)) {
    ids.add(target.id);
    for (const group of groups) {
      if (group.selected.source === target.id || group.selected.target === target.id) {
        ids.add(group.selected.source); ids.add(group.selected.target);
      }
    }
  } else if (target.type === 'edge') {
    const group = groups.find(g => g.key === target.key);
    if (group) { ids.add(group.selected.source); ids.add(group.selected.target); }
  }
  return {
    papers: papers.filter(p => ids.has(p.id)),
    groups: groups.filter(g => ids.has(g.selected.source) && ids.has(g.selected.target)),
  };
}

export const FOCUS_NODE_WIDTH = 282;
export const FOCUS_NODE_HEIGHT = 96;

export function layoutFocus(papers: Paper[], availableWidth: number) {
  const knownYears = papers.flatMap(p => p.year === null ? [] : [p.year]);
  const newest = knownYears.length ? Math.max(...knownYears) : 0;
  const oldest = knownYears.length ? Math.min(...knownYears) : 0;
  const years: (number | null)[] = [...new Set(knownYears)].sort((a,b) => b-a);
  if (!years.length && !papers.some(p => p.year === null)) years.push(newest);
  if (papers.some(p => p.year === null)) years.push(null);
  const maxRow = Math.max(1, ...years.map(year => papers.filter(p => p.year === year).length));
  const width = Math.max(availableWidth, maxRow * 318 + 104);
  const rowY = new Map<number | null, number>();
  let cursorY = 78;
  years.forEach((year, index) => {
    if (index > 0) { const previous = years[index - 1]; cursorY += year !== null && previous !== null ? Math.min(146, 126 + (previous - year - 1) * 5) : 136; }
    rowY.set(year, cursorY);
  });
  const yearY = (year: number | null) => rowY.get(year) ?? 110;
  const positions = new Map<string, { x: number; y: number }>();
  for (const year of years) {
    const row = papers.filter(p => p.year === year).sort((a, b) => a.id.localeCompare(b.id));
    row.forEach((paper, index) => positions.set(paper.id, { x: width / 2 + 25 + (index - (row.length - 1) / 2) * 318, y: yearY(year) }));
  }
  return { width, height: Math.max(230, ...[...positions.values()].map(p => p.y + 82)), positions, years, yearY };
}
export function fitGraphScale(width: number, height: number, viewportWidth: number, viewportHeight: number) {
  return Math.max(.01, Math.min(1, Math.max(1, viewportWidth - 32) / width, Math.max(1, viewportHeight - 32) / height));
}

export function layoutPapers(papers: Paper[], allPapers: Paper[]) {
  const knownYears = allPapers.flatMap(p => p.year === null ? [] : [p.year]);
  const newest = knownYears.length ? Math.max(...knownYears) : 2024;
  const oldest = knownYears.length ? Math.min(...knownYears) : newest;
  const step = 145;
  const yearY = (year: number | null) => year === null ? 110 + (newest - oldest + 1) * step : 110 + (newest - year) * step;
  const positions = new Map<string, { x: number; y: number }>();
  const years = [...new Set(allPapers.map(p => p.year))];
  const graphWidth = Math.max(1120, ...years.map(y => allPapers.filter(p => p.year === y).length * 305 + 220));
  for (const year of years) {
    const row = allPapers.filter(p => p.year === year).sort((a, b) => a.id.localeCompare(b.id));
    row.forEach((p, i) => {
      const offset = row.length === 1 ? (p.is_seed ? 90 : -35) : 0;
      positions.set(p.id, { x: graphWidth / 2 + (i - (row.length - 1) / 2) * 305 + offset, y: yearY(year) });
    });
  }
  return {
    positions: new Map(papers.map(p => [p.id, positions.get(p.id)!])),
    years: Array.from({ length: newest - oldest + 1 }, (_, i) => newest - i),
    yearY, width: graphWidth,
    height: yearY(allPapers.some(p => p.year === null) ? null : oldest) + 135,
  };
}
