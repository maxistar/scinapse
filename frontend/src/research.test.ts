import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeResearch, findPapers } from './research.ts';
import type { Paper } from './graph';

test('restored research rejects malformed storage and empty sessions', () => {
  for (const input of [null, [], { query: 12, seedIds: [], references: [] }, { query: ' ', seedIds: ['missing'], references: [' '] }]) assert.equal(normalizeResearch(input, ['p1']), null);
});
test('research retains references, removes duplicate seeds and discards missing paper IDs', () => {
  assert.deepEqual(normalizeResearch({ query: '  immune cells  ', seedIds: ['p1', 'p1', 'old', 2], references: [' PMID:123 ', 'pmid:123', '10.123/example'] }, ['p1']), {
    query: 'immune cells', seedIds: ['p1'], references: ['pmid:123', '10.123/example'],
  });
  assert.ok(normalizeResearch({ query: '', seedIds: [], references: ['12345'] }, []));
});
test('paper lookup searches metadata and never suggests selected papers', () => {
  const papers = [
    { id: 'p1', title: 'Immune cell atlas', url: 'https://example.org/p1', authors: [{ name: 'A. Smith' }] },
    { id: 'p2', title: 'Lung cancer', url: 'https://example.org/p2', authors: [{ name: 'B. Jones' }] },
  ] as Paper[];
  assert.deepEqual(findPapers(papers, 'SMITH', []).map(p => p.id), ['p1']);
  assert.deepEqual(findPapers(papers, 'https://example.org/p2', []).map(p => p.id), ['p2']);
  assert.deepEqual(findPapers(papers, 'immune', ['p1']), []);
  assert.deepEqual(findPapers(papers, ' ', []), []);
});
