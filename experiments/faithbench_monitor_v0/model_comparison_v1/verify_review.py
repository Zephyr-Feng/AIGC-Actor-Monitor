"""Check assistant quotations and interface observations, without semantic auto-scoring."""
import json
from pathlib import Path

from prepare import ROOT, PRIVATE, canonical_hash, sha256, write_json


def strings(value, path=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, path + '/' + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, path + '/' + str(index))
    elif isinstance(value, str):
        yield path, value


def main():
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    review = read(PRIVATE / 'semantic_review_v1.json')
    packets = read(PRIVATE / 'packets.json')
    checks = []
    for review_id, row in review['reviews'].items():
        copy = read(PRIVATE / 'review_copies' / (review_id + '.json'))
        assert copy['case'] == row['case']
        packet = packets[row['case']]
        actors = []
        tools = [packet['tool_cards']]
        for step in packet['trajectory']['steps']:
            actors.append(step.get('actor_output'))
            actors.extend(json.loads(raw) for raw in step.get('raw_attempts', []))
            if step.get('tool_observation'):
                tools.append(step['tool_observation'])
        if packet.get('current_action'):
            actors.append(packet['current_action']['actor_request'])
        for kind, source in [('model', copy['content']), ('actor', actors), ('tool', tools)]:
            leaves = list(strings(source))
            for index, quote in enumerate(row[kind + '_quotes']):
                matches = [path for path, text in leaves if quote in text]
                assert matches, (review_id, kind, quote)
                checks.append({'review': review_id, 'kind': kind, 'quote_index': index, 'source_paths': matches})
    # The missing final-confidence enum is an integration observation, not an added gold label.
    import sys
    sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
    from actor_b_protocol import parse_action
    action = dict(packets['E2']['trajectory']['steps'][-1]['actor_output'])
    for field, illegal in [('final_confidence', 'medium'), ('final_verdict', 'inconclusive')]:
        candidate = dict(action)
        candidate[field] = illegal
        try:
            parse_action(json.dumps(candidate, ensure_ascii=False), set())
        except ValueError:
            pass
        else:
            raise AssertionError('Expected invalid enum rejection: ' + field)
    action['final_confidence'] = 'low'
    assert parse_action(json.dumps(action, ensure_ascii=False), set()) == action
    target = PRIVATE / 'review_verification.json'
    assert not target.exists()
    write_json(target, {'review_sha256': sha256(PRIVATE / 'semantic_review_v1.json'),
               'quote_checks': checks, 'quote_count': len(checks), 'reviews': len(review['reviews']),
               'confidence_medium_invalid_low_valid': True, 'verdict_inconclusive_invalid': True,
               'semantic_checks_are_assistant_judgment': True, 'model_requests': 0})
    print(json.dumps({'reviews': len(review['reviews']), 'quote_checks': len(checks),
                      'review_sha256': sha256(PRIVATE / 'semantic_review_v1.json'), 'enum_check_passed': True}))


if __name__ == '__main__':
    main()
