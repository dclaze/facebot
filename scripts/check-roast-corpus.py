#!/usr/bin/env python3
"""Validate authored corpus structure and exact-byte review coverage; render reading edition."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'content' / 'mill_valley'

def check(require_reviews=False, render=False):
    raw = (PACK / 'corpus.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    entries = data['entries']
    sources = json.loads((PACK / 'sources.json').read_text())['sources']
    source_ids = {s['id'] for s in sources}
    ids = [e['id'] for e in entries]
    assert len(entries) == 72, f'Expected 72 interactions, got {len(entries)}'
    assert len(set(ids)) == len(ids), 'Duplicate IDs'
    assert len(source_ids) == len(sources), 'Duplicate source IDs'
    spoken = []
    for e in entries:
        assert e['trigger']['type'] == 'visitor_utterance', e['id']
        assert e['trigger']['example'].strip() and e['requirements'], e['id']
        assert e['fallback_id'] in data['fallbacks'], e['id']
        assert e['intensity'] in (0, 1, 2), e['id']
        assert set(e['source_ids']) <= source_ids, e['id']
        assert e['category'] == 'care' or e['source_ids'], f"Missing local anchor: {e['id']}"
        for turn in (e, e['followup']):
            reply, action = turn['reply'], turn['action']
            assert action in ('speak', 'silence'), e['id']
            assert (action == 'silence') == (reply == ''), f"Invalid silence: {e['id']}"
            assert len(reply.split()) <= 30, f"Overlong: {e['id']} ({len(reply.split())})"
            if reply:
                spoken.append(reply)
    assert len(spoken) == len(set(spoken)), 'Duplicate spoken lines'
    coverage = {}
    if require_reviews:
        for role in ('comedy', 'family', 'local'):
            # Initial review is immutable; final review records a full final-file
            # assessment or explicit unchanged-entry carryforward with changed IDs.
            receipt = json.loads((PACK / 'reviews' / f'{role}-final.json').read_text())
            assert receipt['corpus_sha256'] == digest, f'Stale {role} review'
            reviewed = [x['id'] for x in receipt['entries']]
            assert len(reviewed) == len(set(reviewed)) and set(reviewed) == set(ids), f'Incomplete {role} coverage'
            assert all(x['verdict'] == 'keep' for x in receipt['entries']), f'Unresolved {role} findings'
            initial = json.loads((PACK / 'reviews' / f'{role}.json').read_text())
            initial_ids = [x['id'] for x in initial['entries']]
            assert len(initial_ids) == len(set(initial_ids)) and set(initial_ids) == set(ids), f'Incomplete initial {role} review'
            coverage[role] = len(reviewed)
        decisions = json.loads((PACK / 'reviews' / 'editor-decisions.json').read_text())
        assert decisions['final_corpus_sha256'] == digest, 'Stale editor decisions'
        snapshot = (PACK / 'reviews' / 'corpus-initial.json').read_bytes()
        assert hashlib.sha256(snapshot).hexdigest() == decisions['initial_corpus_sha256'], 'Initial snapshot mismatch'
        initial_hashes = {json.loads((PACK / 'reviews' / f'{r}.json').read_text())['corpus_sha256'] for r in coverage}
        assert initial_hashes == {decisions['initial_corpus_sha256']}, 'Initial review mismatch'
        decision_ids = [x['id'] for x in decisions['entries']]
        assert len(decision_ids) == len(set(decision_ids)) and set(decision_ids) == set(ids), 'Incomplete editor dispositions'
    if render:
        lines = ['# Mill Valley roast library', '',
                 '72 original interactions: 64 comic exchanges and 8 care/boundary exchanges. Authored October 25, 2026.', '',
                 'Both turns are conditional examples, never an automatic script. See the [performance and selection guide](../content/mill_valley/README.md) and [machine-readable corpus](../content/mill_valley/corpus.json).', '',
                 'Intensity: 1 = gentle local absurdity; 2 = sharp situation/town satire during welcomed banter; 0 = care takes priority. All visitor turns are synthetic.', '',
                 'Browse: [stairs](#stairs) · [Mount Tam](#tam) · [coffee](#coffee) · [shopping](#shopping) · [getting around](#getting-around) · [arts](#arts) · [Halloween](#halloween) · [heckles](#heckles) · [care and boundaries](#care).', '',
                 f'Corpus SHA-256: `{digest}`.', '']
        last = None
        for e in entries:
            if e['category'] != last:
                last = e['category']
                lines.extend([f'## {last.replace("-", " ").title()}', ''])
            lines.extend([f'### {e["id"]} · intensity {e["intensity"]}', '',
                          f'**Visitor:** {e["trigger"]["example"]}', '',
                          f'**Boo:** {e["reply"] or "[Silence; cancel speech.]"}', '',
                          f'**Visitor:** {e["followup"]["visitor"]}', '',
                          f'**Boo:** {e["followup"]["reply"] or "[Silence; cancel speech.]"}', ''])
            if e['source_ids']:
                refs = [s for s in sources if s['id'] in e['source_ids']]
                lines.extend(['Local anchors: ' + ', '.join(f'[{s["title"]}]({s["url"]})' for s in refs) + '.', ''])
        (ROOT / 'docs' / 'MILL_VALLEY_ROAST_LIBRARY.md').write_text('\n'.join(lines))
    print(json.dumps({'interactions':len(entries),'spoken_turns':len(spoken),'sources':len(sources),'review_coverage':coverage,'corpus_sha256':digest,'rendered':render}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-reviews', action='store_true')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    check(args.require_reviews, args.render)
