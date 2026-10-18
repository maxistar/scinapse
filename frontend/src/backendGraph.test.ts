import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { evidenceDescription, groupEdges, focusSubgraph, layoutFocus, layoutPapers, passesRelevance, qualityScore, relationshipLabel, type GraphData } from './graph.ts';
import { researchStorageKey } from './research.ts';

const data = JSON.parse(readFileSync(new URL('../../graph.json', import.meta.url), 'utf8')) as GraphData;
const types = [...new Set(data.edges.map(edge => edge.type))];

test('backend relationship types retain every pair and select its strongest display score', () => {
  assert.deepEqual(new Set(types), new Set(['citation_overlap', 'shared_author', 'similar_to']));
  assert.equal(data.edges.length, 56);
  const groups = groupEdges(data.edges, types);
  assert.equal(groups.length, 51);
  assert.equal(groups.flatMap(group => group.all).length, 56);
  for (const group of groups) assert.equal(group.selected.display_score.value, Math.max(...group.all.map(edge => edge.display_score.value ?? -1)));
  assert.equal(relationshipLabel('citation_overlap'), 'Citation overlap');
  assert.equal(groupEdges(data.edges, ['shared_author']).flatMap(group => group.all).length, 11);
});
test('backend paper focus includes neighbours from the new types and produces valid positions', () => {
  const focus = focusSubgraph(data.nodes, data.edges, { type: 'paper', id: 'paper_001' }, types);
  assert.equal(focus.papers.length, 7);
  for (const layout of [layoutPapers(data.nodes, data.nodes), layoutFocus(focus.papers, 800)]) {
    for (const point of layout.positions.values()) assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y));
  }
});
test('missing backend quality stays unknown without disabling relevance filtering', () => {
  assert.ok(data.nodes.every(paper => qualityScore(paper) === null));
  assert.equal(data.nodes.filter(paper => passesRelevance(paper, 0)).length, 35);
  assert.deepEqual(data.nodes.filter(paper => passesRelevance(paper, 80)).map(paper => paper.id), data.nodes.filter(paper => paper.is_seed || (paper.relevance.score !== null && paper.relevance.score >= .8)).map(paper => paper.id));
  assert.equal(data.nodes.filter(paper => paper.is_seed).length, 5);
});
test('backend author evidence renders names, reference evidence handles empty records, and provenance is retained', () => {
  const authors = data.evidence.find(e => e.type === 'author_list')!;
  assert.ok(evidenceDescription(authors, data.nodes).includes(authors.author_names![0]));
  assert.ok(!evidenceDescription(authors, data.nodes).includes('References:'));
  const empty = data.evidence.find(e => e.type === 'reference_list' && !e.referenced_paper_ids?.length)!;
  assert.equal(evidenceDescription(empty, data.nodes), 'No references included in this evidence record.');
  const references = data.evidence.find(e => e.referenced_paper_ids?.length)!;
  assert.ok(evidenceDescription(references, data.nodes).includes(data.nodes.find(paper => paper.id === references.referenced_paper_ids![0])!.title));
  assert.equal(authors.provenance, 'openalex');
});
test('artifact storage is isolated from demo sessions and backend warnings resolve to real nodes', () => {
  assert.notEqual(researchStorageKey(data.exploration_id), 'scinapse-research:v1');
  assert.notEqual(researchStorageKey(data.exploration_id), researchStorageKey('another-exploration'));
  assert.equal(data.warnings.length, 7);
  for (const warning of data.warnings) if (warning.node_id) assert.ok(data.nodes.some(paper => paper.id === warning.node_id));
});
