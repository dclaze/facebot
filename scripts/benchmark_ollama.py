#!/usr/bin/env python3
"""Synthetic host-only generation timing. Never claims audible reply latency."""
import argparse
import json
import math
import time
import urllib.request

PROMPTS = (
    'May I have some candy?',
    'Are you a real ghost?',
    'Why can I only take one piece?',
    'What is your Halloween costume?',
    'Tell me a very short spooky joke.',
)
SYSTEM = ('You are a witty Halloween ghost. Give one short family-safe sentence, '
          'at most 18 words. Tease situations or yourself, never personal traits. '
          'No threats, adult content, or claims to see anything. No tools.')


def percentile(values, fraction):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def measure(base, model, prompt):
    body = {'model': model, 'stream': True, 'think': False,
            'messages': [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': prompt}],
            'options': {'num_predict': 64, 'temperature': 0.7, 'num_ctx': 2048}}
    request = urllib.request.Request(base + '/api/chat',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    first = sentence = None
    content = ''
    with urllib.request.urlopen(request, timeout=90) as response:
        for line in response:
            event = json.loads(line)
            if event.get('error'):
                raise RuntimeError(event['error'])
            token = event.get('message', {}).get('content', '')
            if token:
                elapsed = (time.monotonic() - start) * 1000
                content += token
                if first is None:
                    first = elapsed
                if sentence is None and any(c in content for c in '.!?'):
                    sentence = elapsed
            if event.get('done'):
                if not content.strip():
                    raise RuntimeError('Empty generated response')
                return {'first_token_ms': first, 'first_sentence_ms': sentence,
                        'complete_ms': (time.monotonic() - start) * 1000,
                        'output_tokens': event.get('eval_count'),
                        'load_ms': event.get('load_duration', 0) / 1e6}
    raise RuntimeError('Stream ended without completion')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='qwen3.5:9b')
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    rows = []
    for i in range(args.samples + 1):
        try:
            row = measure(args.url, args.model, PROMPTS[i % len(PROMPTS)])
        except Exception as error:
            row = {'error_type': type(error).__name__}
        row.update(sample=i, phase='initial' if i == 0 else 'warm')
        rows.append(row)
        print(json.dumps(row), flush=True)
    warm = [r for r in rows[1:] if 'error_type' not in r]
    summary = {'evidence': 'synthetic host LLM component; not speech latency',
               'model': args.model, 'samples': args.samples,
               'failures': len(rows) - sum('error_type' not in r for r in rows)}
    for metric in ('first_token_ms', 'first_sentence_ms', 'complete_ms'):
        values = [r[metric] for r in warm if r[metric] is not None]
        summary[metric] = {'n': len(values), 'p50': percentile(values, .5),
                           'p95': percentile(values, .95)}
    print(json.dumps(summary), flush=True)
    return 1 if summary['failures'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
