#!/usr/bin/env python3
"""Local owner prompt tuning; no server/app restart and no visitor speech storage."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.coaching import read, save

parser = argparse.ArgumentParser(description=__doc__)
commands = parser.add_subparsers(dest='command', required=True)
commands.add_parser('show')
replace = commands.add_parser('set', help='Replace current rules with a compact distilled set')
replace.add_argument('rules', nargs='+')
commands.add_parser('clear')
rollback = commands.add_parser('rollback')
rollback.add_argument('revision', type=int)
args = parser.parse_args()
try:
    state = read()
    if args.command == 'set': state = save(args.rules)
    elif args.command == 'clear': state = save([])
    elif args.command == 'rollback':
        match = next((r for r in state['history'] if r['revision'] == args.revision), None)
        if match is None: raise ValueError('Revision is not in retained history')
        state = save(match['rules'])
    print(json.dumps({'revision': state['revision'], 'rules': state['rules']}, indent=2))
except (OSError, ValueError, KeyError) as error:
    parser.exit(1, str(error) + '\n')
