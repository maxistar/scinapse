import type { GraphData, Paper } from './graph';
import type { ResearchSession } from './research';

export interface BuildRequest { question: string; seeds: string[] }
export interface ResearchJob {
  id: string; status: 'queued' | 'running' | 'completed' | 'failed';
  stage: number; total_stages: number; message: string;
  profile: string; assessments_enabled: boolean;
  question: string; created_at: number; finished_at: number | null;
  status_url: string; graph_url: string | null;
}
export function normalizeDoi(value: string): string | null {
  const doi = value.trim().replace(/^(?:https?:\/\/)?(?:dx\.)?doi\.org\//i, '').replace(/^doi:\s*/i, '');
  return /^10\.\d{4,9}\/[^\s]+$/i.test(doi) && doi.length <= 500 ? doi : null;
}
export function buildRequest(input: ResearchSession, papers: Paper[]): BuildRequest {
  const question = input.query.trim();
  if (question.length < 3 || question.length > 2000) throw new Error('Enter a research question (3–2000 characters).');
  const references = [...input.references, ...input.seedIds.map(id => {
    const paper = papers.find(p => p.id === id);
    return paper?.identifiers?.doi || paper?.url || '';
  })];
  const seeds: string[] = [];
  for (const reference of references) {
    const doi = normalizeDoi(reference);
    if (!doi) throw new Error('Starting papers must have a DOI. Use a DOI or doi.org link; PMID and title-only lookup are not available yet.');
    if (!seeds.some(seed => seed.toLowerCase() === doi.toLowerCase())) seeds.push(doi);
  }
  if (!seeds.length) throw new Error('Add at least one starting paper using its DOI.');
  if (seeds.length > 10) throw new Error('Use up to 10 starting papers per search.');
  return { question, seeds };
}
async function request<T>(path: string, signal: AbortSignal, body?: unknown): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, { method: body ? 'POST' : 'GET', signal: AbortSignal.any([signal, AbortSignal.timeout(20000)]), headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined }); }
  catch (error) {
    if (signal.aborted) throw error;
    throw new Error('Cannot reach the research server. Check that the backend is running, then retry.');
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(typeof detail === 'string' ? detail : response.status === 422 ? 'Check your research question and starting DOIs.' : `Research server returned an error (${response.status}). Please retry.`);
  }
  return response.json();
}
export const startResearch = (body: BuildRequest, signal: AbortSignal) => request<ResearchJob>('/explorations', signal, body);
export const listResearch = (signal: AbortSignal) => request<{ tasks: ResearchJob[]; total: number }>('/explorations', signal);
export const getResearch = (id: string, signal: AbortSignal) => request<ResearchJob>(`/explorations/${encodeURIComponent(id)}`, signal);
export async function getGraph(id: string, signal: AbortSignal): Promise<GraphData> {
  const data = await request<GraphData>(`/explorations/${encodeURIComponent(id)}/graph`, signal);
  if (!data || !data.exploration_id || !data.research_question || !Array.isArray(data.nodes) || !data.nodes.length || !Array.isArray(data.edges) || !Array.isArray(data.evidence) || !Array.isArray(data.warnings)) throw new Error('The backend returned an incomplete graph. Please retry the search.');
  return data;
}
