"""Small context/paired-statistics helper and an entirely synthetic experiment runner.

No shell, network, model imports or real execution backend. Local mock limits are
regression checks, NOT an independent security boundary against this file's owner.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[4]
STORE = REPO / 'docs' / 'research_loop'
MOCK_LIMIT = 3
FIELDS = {'id', 'mode', 'candidate', 'hypothesis', 'alternative', 'change',
          'prediction', 'falsifier', 'next_if_pass', 'next_if_fail', 'budget_units'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def history(root):
    path = root / 'experiments.jsonl'
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf8').splitlines():
        row = json.loads(line)
        if row.get('track') not in {'project', 'mock'} or not isinstance(row.get('id'), str):
            raise ValueError('invalid ledger row; inspect original, do not reconstruct')
        rows.append(row)
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate ledger IDs')
    return rows


def context(root, recent=2, track='project'):
    if not 0 <= recent <= 5 or track not in {'mock', 'project'}:
        raise ValueError('recent must be 0..5; track must be project or mock')
    state = read_json(root / 'state.json')
    rows = [r for r in history(root) if r['track'] == track]
    observed = [r for r in rows if r.get('metrics', {}).get('net_repairs') is not None] if track == 'mock' else []
    best = max(observed, key=lambda r: r['metrics']['net_repairs'], default=None)
    brief_fields = {'id', 'hypothesis', 'alternative', 'change', 'result', 'validation',
                    'evidence', 'decision', 'next', 'metrics', 'artifacts'}
    result = {'state': {k: v for k, v in state.items() if k not in {'progress_marker', 'best_development'}}, 'track': track,
              'recent': [{k: v for k, v in r.items() if k in brief_fields}
                         for r in (rows[-recent:] if recent else [])],
              'best_observed': ({k: best[k] for k in ('id', 'metrics', 'decision', 'artifacts')}
                                if best else None) if track == 'mock' else state.get('best_development')}
    if root.resolve() == STORE.resolve():
        # Read the current head, not the historical running entries below it.
        with (REPO / 'docs/PROJECT_PROGRESS.md').open(encoding='utf8') as progress:
            marker = next((line.rstrip('\r\n') for line in progress
                           if line.startswith('**') and not line.startswith('**research-loop ')), '')
        result['latest_research_marker'] = marker.split('**')[1] if '**' in marker else marker
        result['snapshot_current'] = marker == state.get('progress_marker')
    return result


def simulate(candidate):
    if candidate not in {'format-only', 'evidence-bound'}:
        raise ValueError('unknown mock candidate')
    rows = []
    for i in range(4):
        before = i >= 2
        after = True if candidate == 'evidence-bound' else i == 0
        rows.append({'id': f'toy-{i}', 'source_group': f'synthetic-{i}',
                     'split': 'development', 'correct_before': before,
                     'self_review_correct': before, 'correct_after': after,
                     'format_valid': True, 'unknown_case': i == 3,
                     'unknown_preserved': i != 3 or candidate == 'evidence-bound'})
    return rows


def metrics(rows, expected_ids=None):
    if not isinstance(rows, list) or not rows:
        raise ValueError('nonempty paired row list required')
    boolean_fields = ('correct_before', 'self_review_correct', 'correct_after',
                      'format_valid', 'unknown_case', 'unknown_preserved')
    ids, splits = set(), {}
    for row in rows:
        if not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
            raise ValueError('missing/duplicate paired ID')
        ids.add(row['id'])
        group, split = row.get('source_group'), row.get('split')
        if not isinstance(group, str) or not group or split not in {'development', 'independent'}:
            raise ValueError('source group and evaluation split required')
        if group in splits and splits[group] != split:
            raise ValueError('source leakage across evaluation splits')
        splits[group] = split
        if any(type(row.get(key)) is not bool for key in boolean_fields):
            raise ValueError('outcomes must be explicit booleans, not missing or inferred')
    if expected_ids is not None:
        if (not isinstance(expected_ids, list) or
                any(not isinstance(i, str) for i in expected_ids) or
                len(set(expected_ids)) != len(expected_ids) or set(expected_ids) != ids):
            raise ValueError('paired IDs differ from frozen expected list')
    repaired = sum(not r['correct_before'] and r['correct_after'] for r in rows)
    harmed = sum((r['correct_before'] and not r['correct_after']) or
                 (r['unknown_case'] and not r['unknown_preserved']) for r in rows)
    wins = {r['source_group'] for r in rows if r['correct_after'] and not r['self_review_correct']}
    losses = {r['source_group'] for r in rows if r['self_review_correct'] and not r['correct_after']}
    return {'rows': len(rows), 'source_groups': len(splits), 'repairs': repaired,
            'harmful_edits': harmed, 'net_repairs': repaired - harmed,
            'format_valid': sum(r['format_valid'] for r in rows),
            'monitor_win_groups': len(wins - losses), 'self_review_win_groups': len(losses - wins),
            'mixed_groups': len(wins & losses),
            'unknown_preserved': sum(r['unknown_case'] and r['unknown_preserved'] for r in rows)}


def validate_proposal(p):
    if not isinstance(p, dict) or set(p) != FIELDS:
        raise ValueError('proposal fields differ; command/output/promotion fields are not supported')
    if p['mode'] != 'mock':
        raise ValueError('this helper supports mock only; use existing authorized runners for real tasks')
    if not isinstance(p['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', p['id']):
        raise ValueError('use a short lowercase experiment ID, never a path')
    if p['candidate'] not in {'format-only', 'evidence-bound'}:
        raise ValueError('mock runner only accepts the two built-in synthetic strategies')
    if type(p['budget_units']) is not int or p['budget_units'] != 1:
        raise ValueError('one mock unit per experiment; no real budget may be supplied')
    for key in FIELDS - {'budget_units'}:
        if not isinstance(p[key], str) or not p[key].strip() or len(p[key]) > 600:
            raise ValueError(f'{key}: nonempty short text required')


def safe_local_path(root, path):
    if path.is_symlink() or path.resolve() != root.resolve() / path.relative_to(root):
        raise ValueError('redirected output path refused')


@contextmanager
def writer(root):
    root = Path(root).absolute()
    read_json(root / 'state.json')
    for path in (root / 'mock', root / 'experiments.jsonl', root / '.writer.lock'):
        safe_local_path(root, path)
    # Exclusive writer; on a crash leave evidence, never silently restart/replay.
    try:
        lock = (root / '.writer.lock').open('x', encoding='utf8')
    except FileExistsError as exc:
        raise ValueError('writer active or interrupted; inspect before resuming') from exc
    try:
        with lock:
            yield root, history(root)
    finally:
        (root / '.writer.lock').unlink()


def record_analysis(root, record):
    required = {'id', 'track', 'hypothesis', 'change', 'result', 'validation', 'evidence', 'decision', 'next'}
    if not isinstance(record, dict) or set(record) != required or record['track'] != 'project':
        raise ValueError('analysis record fields differ; no authorization or promotion fields')
    if not isinstance(record['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', record['id']):
        raise ValueError('invalid record ID')
    for key in required - {'evidence'}:
        if not isinstance(record[key], str) or not record[key].strip() or len(record[key]) > 900:
            raise ValueError(f'{key}: short nonempty text required')
    if record['decision'] not in {'reject', 'continue', 'candidate', 'stop'}:
        raise ValueError('recording is not baseline promotion')
    if not isinstance(record['evidence'], list) or not record['evidence']:
        raise ValueError('evidence paths required')
    for ref in record['evidence']:
        if not isinstance(ref, str):
            raise ValueError('evidence must name existing project files')
        path = (REPO / ref).resolve()
        if not path.is_relative_to(REPO) or not path.is_file():
            raise ValueError('evidence outside project or missing')
    with writer(root) as (root, rows):
        if any(r['id'] == record['id'] for r in rows):
            raise ValueError('record already exists; append a correction with a new ID')
        result = dict(record, timestamp=datetime.now(timezone.utc).isoformat())
        with (root / 'experiments.jsonl').open('a', encoding='utf8') as out:
            out.write(dump(result) + '\n')
    return result


def run_mock(root, proposal):
    validate_proposal(proposal)
    with writer(root) as (root, rows):
        if any(r['id'] == proposal['id'] for r in rows):
            raise ValueError('experiment already recorded; do not rerun')
        if sum(r['budget_units'] for r in rows if r['track'] == 'mock') >= MOCK_LIMIT:
            raise ValueError('mock session budget exhausted; stop, do not reset history')
        run = root / 'mock' / proposal['id']
        try:
            run.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise ValueError('existing/interrupted artifacts; never overwrite') from exc
        raw = simulate(proposal['candidate'])
        stats = metrics(raw, [f'toy-{i}' for i in range(4)])
        passed = stats['harmful_edits'] == 0 and stats['monitor_win_groups'] >= 2
        record = dict(proposal, track='mock', timestamp=datetime.now(timezone.utc).isoformat(),
                      metrics=stats, decision='candidate_needs_independent_validation' if passed else 'reject',
                      next=proposal['next_if_pass'] if passed else proposal['next_if_fail'],
                      baseline_promoted=False, evidence='synthetic_only',
                      artifacts=f'mock/{proposal["id"]}')
        for name, value in [('proposal.json', proposal), ('paired.json', raw), ('result.json', record)]:
            with (run / name).open('x', encoding='utf8') as out:
                out.write(dump(value) + '\n')
        with (root / 'experiments.jsonl').open('a', encoding='utf8') as out:
            out.write(dump(record) + '\n')
        return record


def main():
    sys.stdout.reconfigure(encoding='utf8')
    sys.stderr.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    ctx = commands.add_parser('context')
    ctx.add_argument('--recent', type=int, default=2)
    ctx.add_argument('--track', choices=['project', 'mock'], default='project')
    mock = commands.add_parser('mock')
    mock.add_argument('--proposal', type=Path, required=True)
    record = commands.add_parser('record')
    record.add_argument('--record', type=Path, required=True)
    summary = commands.add_parser('summarize')
    summary.add_argument('--paired', type=Path, required=True)
    summary.add_argument('--expected', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'context':
            result = context(STORE, args.recent, args.track)
        elif args.action == 'mock':
            result = run_mock(STORE, read_json(args.proposal))
        elif args.action == 'record':
            result = record_analysis(STORE, read_json(args.record))
        else:
            result = metrics(read_json(args.paired), read_json(args.expected))
        print(dump(result))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f'REFUSED: {exc}\n')


if __name__ == '__main__':
    main()
