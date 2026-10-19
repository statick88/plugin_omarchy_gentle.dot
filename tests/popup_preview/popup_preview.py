#!/usr/bin/env python3
"""Finite, synthetic state preview for the owned popup; it never contacts Gentle Dot."""
import argparse
import json


DISCONNECTED = {
    'canSend': False,
    'canStop': False,
    'connectionState': 'disconnected',
    'messages': [],
    'modelLabel': 'Gentle Dot',
    'statusText': 'Connect Gentle Dot to chat here. Until then, open the official app.',
    'streaming': False,
}


def synthetic_connected():
    return {
        'canSend': True,
        'canStop': False,
        'connectionState': 'connected',
        'messages': [
            {'id': 'welcome', 'role': 'assistant', 'text': 'Synthetic preview only.'},
            {'id': 'draft', 'role': 'user', 'text': '<plain text, not markup>'},
        ],
        'modelLabel': 'Preview model',
        'statusText': 'Synthetic controller connected; no network is used.',
        'streaming': False,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Print a finite synthetic popup state; this is not a backend client.')
    parser.add_argument('--state', action='store_true', help='print the disconnected default state')
    parser.add_argument('--synthetic-connected', action='store_true',
                        help='print the fixture-only connected state')
    args = parser.parse_args()
    if args.state == args.synthetic_connected:
        parser.error('choose exactly one state')
    print(json.dumps(synthetic_connected() if args.synthetic_connected else DISCONNECTED,
                     separators=(',', ':')))


if __name__ == '__main__':
    main()
