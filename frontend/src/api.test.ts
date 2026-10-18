import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRequest, normalizeDoi, getResearch, startResearch, getGraph } from './api.ts';
import type { Paper } from './graph';

test('discovery requires a question and seed DOIs, normalizes and deduplicates identifiers', () => {
  assert.equal(normalizeDoi(' https://doi.org/10.1126/science.aad0501 '), '10.1126/science.aad0501');
  assert.equal(normalizeDoi('https://pubmed.ncbi.nlm.nih.gov/27124452/'), null);
  const input = { query: 'Melanoma immune cells?', seedIds: ['p1'], references: ['DOI:10.1126/science.aad0501'] };
  const papers = [{ id: 'p1', identifiers: { doi: '10.1126/science.aad0501' } }] as Paper[];
  assert.deepEqual(buildRequest(input, papers), { question: input.query, seeds: ['10.1126/science.aad0501'] });
  assert.throws(() => buildRequest({ ...input, query: ' ' }, papers), /question/);
  assert.throws(() => buildRequest({ query: input.query, seedIds: [], references: [] }, papers), /at least one/);
  assert.throws(() => buildRequest({ ...input, references: ['not a DOI'] }, papers), /DOI/);
});
test('API client posts research, retrieves a new graph, and reports expired jobs', async () => {
  const original = globalThis.fetch;
  const calls: {url: string; body: unknown}[] = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), body: options?.body ? JSON.parse(String(options.body)) : null });
    if (String(url).includes('expired')) return new Response(JSON.stringify({ detail: 'Session expired' }), { status: 404 });
    if (String(url).endsWith('/graph')) return Response.json({ exploration_id: 'new', research_question: 'New question', nodes: [{ id: 'new-paper' }], edges: [], evidence: [], warnings: [] });
    return Response.json({ id: 'new-job', status: 'queued' });
  };
  try {
    const signal = new AbortController().signal;
    await startResearch({ question: 'New question', seeds: ['10.1234/test'] }, signal);
    assert.equal(calls[0].url, '/api/explorations');
    assert.deepEqual(calls[0].body, { question: 'New question', seeds: ['10.1234/test'] });
    assert.equal((await getGraph('new-job', signal)).nodes[0].id, 'new-paper');
    await assert.rejects(getResearch('expired', signal), /Session expired/);
  } finally { globalThis.fetch = original; }
});
