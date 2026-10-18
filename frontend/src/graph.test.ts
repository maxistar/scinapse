import test from 'node:test';
import assert from 'node:assert/strict';
import { groupEdges, layoutPapers, connectionGeometry, edgeWidth, passesRelevance, qualityScore, relevanceScore, scorePalette, focusSubgraph, layoutFocus, fitGraphScale, type Edge, type Paper } from './graph.ts';

const edge = (id: string, source: string, target: string, type: string, value: number | null) => ({ id, source, target, type, directed: type === 'cites', display_score: { value } }) as Edge;
test('selects per unordered pair, preserves direction, and filters before selection', () => {
  const edges = [edge('a', 'new', 'old', 'cites', .9), edge('b', 'old', 'new', 'similar_to', .8)];
  const groups = groupEdges(edges, ['cites', 'similar_to']);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].all.length, 2);
  assert.equal(groups[0].selected.source, 'new');
  assert.equal(groupEdges(edges, ['similar_to'])[0].selected.id, 'b');
});
test('ignores null display scores and resolves ties by edge id', () => {
  assert.equal(groupEdges([edge('z', 'a', 'b', 'cites', null)], ['cites']).length, 0);
  assert.equal(groupEdges([edge('z', 'a', 'b', 'cites', .9), edge('a', 'b', 'a', 'cites', .9)], ['cites'])[0].selected.id, 'a');
});
test('timeline is proportional and positions stay fixed when filtering', () => {
  const papers = [{ id: 'a', year: 2024 }, { id: 'b', year: 2023 }, { id: 'c', year: 2020 }, { id: 'd', year: null }] as Paper[];
  const full = layoutPapers(papers, papers);
  const subset = layoutPapers([papers[1]], papers);
  assert.deepEqual(subset.positions.get('b'), full.positions.get('b'));
  assert.equal(full.positions.get('c')!.y - full.positions.get('b')!.y, 3 * 145);
  assert.ok(full.positions.get('d')!.y > full.positions.get('c')!.y);
});

test('edge width follows display score rather than raw relationship strength', () => {
  const scored = (value: number | null) => ({ strength: { value: .99 }, display_score: { value } }) as Edge;
  assert.ok(edgeWidth(scored(.9)) > edgeWidth(scored(.2)));
  assert.equal(edgeWidth(scored(.9)), 5.05);
  assert.equal(edgeWidth(scored(0)), 1);
  assert.equal(edgeWidth(scored(null)), 1.2);
  assert.equal(edgeWidth(scored(2)), 1.2);
  assert.equal(edgeWidth({ strength: { value: 0 }, display_score: { value: .9 } } as Edge), edgeWidth(scored(.9)));
});

test('node relevance colors are independent of paper quality and preserve unknown scores', () => {
  const paper = { research_assessment: { overall_score: null }, relevance: { score: 1 } } as Paper;
  assert.equal(qualityScore(paper), null);
  assert.equal(relevanceScore(paper), 1);
  assert.equal(scorePalette(relevanceScore(paper)).accent, 'rgb(45, 137, 93)');
  paper.relevance.score = 0;
  paper.research_assessment.overall_score = 1;
  assert.equal(scorePalette(relevanceScore(paper)).accent, 'rgb(197, 85, 75)');
  paper.relevance.score = null;
  assert.equal(relevanceScore(paper), null);
  assert.equal(scorePalette(relevanceScore(paper)).background, '#ffffff');
  paper.relevance.score = 88;
  assert.equal(relevanceScore(paper), null);
});

test('wide publication-year rows fit inside the graph bounds', () => {
  const papers = Array.from({ length: 7 }, (_, i) => ({ id: `paper_${i}`, year: 2025, is_seed: false })) as Paper[];
  const layout = layoutPapers(papers, papers);
  for (const position of layout.positions.values()) {
    assert.ok(position.x - 112 >= 0);
    assert.ok(position.x + 112 <= layout.width);
  }
});

test('paper focus contains direct neighbours and preserves relationships between them', () => {
  const papers = ['a','b','c','d'].map(id => ({ id })) as Paper[];
  const edges = [edge('ab','a','b','cites',.9), edge('ac','a','c','cites',.8), edge('bc','b','c','similar_to',.7), edge('cd','c','d','cites',.6)];
  const focus = focusSubgraph(papers, edges, { type: 'paper', id: 'a' }, ['cites','similar_to']);
  assert.deepEqual(focus.papers.map(p=>p.id), ['a','b','c']);
  assert.equal(focus.groups.length, 3);
  const pair = focusSubgraph(papers, edges, { type: 'edge', key: 'a::b' }, ['cites']);
  assert.deepEqual(pair.papers.map(p=>p.id), ['a','b']);
  assert.equal(pair.groups.length, 1);
  assert.equal(focusSubgraph(papers,edges,{type:'paper',id:'d'},['similar_to']).papers.length,1);
});

test('focus graph keeps cards readable and orders years without distant empty bands', () => {
  const papers = [{id:'new',year:2026},{id:'old',year:2015},{id:'undated',year:null}] as Paper[];
  const layout = layoutFocus(papers, 700);
  assert.ok(layout.positions.get('new')!.y < layout.positions.get('old')!.y);
  assert.ok(layout.positions.get('old')!.y < layout.positions.get('undated')!.y);
  assert.ok(layout.positions.get('old')!.y - layout.positions.get('new')!.y <= 240);
  for (const position of layout.positions.values()) {
    assert.ok(position.x - 141 >= 0);
    assert.ok(position.x + 141 <= layout.width);
  }
});

test('connections attach at side midpoints in overview and focus layouts', () => {
  for (const [width,height] of [[224,72],[282,150]]) {
    const a={x:400,y:100};
    for (const b of [{x:800,y:100},{x:500,y:300},{x:500,y:900},{x:200,y:-500}]) {
      const geometry=connectionGeometry(a,b,width,height);
      for (const [point,center] of [[geometry.start,a],[geometry.end,b]]) {
        assert.ok((point.x===center.x && Math.abs(point.y-center.y)===height/2) || (point.y===center.y && Math.abs(point.x-center.x)===width/2));
      }
    }
    const side=connectionGeometry(a,{x:500,y:900},width,height);
    assert.equal(side.start.y,a.y);
    assert.equal(side.end.y,900);
  }
});

test('focus graph fits large and small layouts inside its viewport', () => {
  for (const [width,height,vw,vh] of [[2000,1400,800,600],[760,430,800,650],[418,430,370,760]]) {
    const scale=fitGraphScale(width,height,vw,vh);
    assert.ok(width*scale<=vw-32+.001);
    assert.ok(height*scale<=vh-32+.001);
    assert.ok(scale<=1);
  }
});


test('relevance thresholds include boundary scores, exclude unknown candidates, and retain seeds', () => {
  const paper = (score: number | null, is_seed = false) => ({ is_seed, relevance: { score }, research_assessment: { overall_score: null } }) as Paper;
  assert.ok(passesRelevance(paper(null), 0));
  assert.ok(passesRelevance(paper(0), 0));
  assert.ok(passesRelevance(paper(.8), 80));
  assert.ok(!passesRelevance(paper(.79), 80));
  assert.ok(!passesRelevance(paper(null), 80));
  assert.ok(!passesRelevance(paper(2), 80));
  assert.ok(passesRelevance(paper(null, true), 100));
  assert.ok(passesRelevance(paper(.1, true), 100));
  assert.ok(passesRelevance(paper(1), 100));
});
