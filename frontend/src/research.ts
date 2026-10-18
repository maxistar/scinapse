import type { Paper } from './graph';

export interface ResearchSession {
  query: string;
  seedIds: string[];
  references: string[];
}

export function normalizeResearch(value: unknown, validIds: string[]): ResearchSession | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.query !== 'string' || !Array.isArray(candidate.seedIds) || !Array.isArray(candidate.references)) return null;
  const query = candidate.query.trim().slice(0, 2000);
  const seedIds = [...new Set(candidate.seedIds.filter((id): id is string => typeof id === 'string' && validIds.includes(id)))];
  const references = [...new Map(candidate.references.filter((ref): ref is string => typeof ref === 'string' && !!ref.trim()).map(ref => { const clean = ref.trim().slice(0, 500); return [clean.toLowerCase(), clean]; })).values()];
  return query || seedIds.length || references.length ? { query, seedIds, references } : null;
}

export function researchStorageKey(explorationId: string) { return `scinapse-research:v2:${explorationId}`; }

export function readResearch(validIds: string[], explorationId: string): ResearchSession | null {
  try { return normalizeResearch(JSON.parse(localStorage.getItem(researchStorageKey(explorationId)) || 'null'), validIds); }
  catch { return null; }
}

export function findPapers(papers: Paper[], input: string, selected: string[]): Paper[] {
  const search = input.trim().toLowerCase();
  if (!search) return [];
  return papers.filter(p => !selected.includes(p.id) && `${p.title} ${p.id} ${p.url} ${p.authors.map(a => a.name).join(' ')}`.toLowerCase().includes(search)).slice(0, 5);
}
