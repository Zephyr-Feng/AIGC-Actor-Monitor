"""Convert published FAVA training annotations, without generating missing labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

TYPES = {'entity', 'relation', 'contradictory', 'invented', 'subjective', 'unverifiable'}
INSTRUCTION = re.compile(r'\nPlease identify all the errors in the following (?:passage|text)[^\n]*\n(?:Text: |\[Text\] )')
REFERENCES = re.compile(r'^Reference\s*\[(\d+)\]: ', re.M)


def project(node, omit):
    if node.tag == omit:
        return ''
    return (node.text or '') + ''.join(project(c, omit) + (c.tail or '') for c in node)


def convert(row, index):
    if not isinstance(row, dict) or set(row) != {'prompt', 'completion'}:
        raise ValueError('unexpected_fields')
    prompt, completion = row['prompt'], row['completion']
    if not isinstance(prompt, str) or not isinstance(completion, str):
        raise ValueError('non_string_fields')
    boundaries = list(INSTRUCTION.finditer(prompt))
    if len(boundaries) != 1:
        raise ValueError('instruction_boundary')
    boundary = boundaries[0]
    references, answer = prompt[:boundary.start()], prompt[boundary.end():]
    matches = list(REFERENCES.finditer(references))
    if not matches or references[:matches[0].start()] != 'Read the following references:\n':
        raise ValueError('reference_header')
    cards = []
    for i, match in enumerate(matches):
        if int(match[1]) != i + 1:
            raise ValueError('reference_sequence')
        end = matches[i + 1].start() if i + 1 < len(matches) else len(references)
        text = references[match.end():end].rstrip('\n')
        if not text.strip():
            raise ValueError('empty_reference')
        cards.append({'id': f'E{i+1:03d}', 'text': text, 'original_reference': match[1]})
    try:
        tree = ET.fromstring('<root>' + completion.replace('&', '&amp;') + '</root>')
    except ET.ParseError as exc:
        raise ValueError('malformed_annotation') from exc
    if any(n.tag not in TYPES | {'root', 'mark', 'delete'} or n.attrib for n in tree.iter()):
        raise ValueError('unknown_tag_or_attribute')
    if any(n.tag not in TYPES for n in tree):
        raise ValueError('untyped_edit')
    for node in tree:
        if any(c.tag not in {'mark', 'delete'} or len(c) for c in node):
            raise ValueError('nested_annotation')
    if project(tree, 'mark') != answer:
        raise ValueError('answer_reconstruction_mismatch')
    issues = []
    cursor = len(tree.text or '')
    for node in tree:
        quote = project(node, 'mark')
        explicit = any(c.tag in {'mark', 'delete'} for c in node)
        replacement = project(node, 'delete') if explicit else None
        issue = {'author_type': node.tag, 'start': cursor, 'end': cursor + len(quote),
                 'quote': quote, 'replacement': replacement,
                 'explicit_edit': explicit, 'evidence_ids': None, 'reason': None}
        assert answer[issue['start']:issue['end']] == quote
        issues.append(issue)
        cursor += len(quote) + len(node.tail or '')
    # Unmarked text is not automatically certified as supported or error-free.
    edited = project(tree, 'delete')
    complete_edits = bool(issues) and all(i['explicit_edit'] for i in issues)
    return {'id': f'fava:train:{index:06d}', 'source_dataset': 'fava-uw/fava-data',
            'source_file': 'training.json', 'source_record_index': index - 1,
            'source_split': 'published_training_file', 'new_split_allocation': False,
            'annotation_origin': 'author_synthetic', 'human_gold': False,
            'approved_for_training': False, 'semantic_verified': False,
            'input': {'审核范围': '按作者已有标签定位错误并应用明确编辑；缺失字段不补写。',
                      '证据卡': cards, '待核回答': answer},
            'supervision': {'issues': issues, 'edit_projection': edited,
                            'corrected_answer': edited if complete_edits else None,
                            'all_flagged_issues_have_explicit_edits': complete_edits,
                            'explanation_language': None, 'protected_content': None,
                            'full_feedback_contract_complete': False},
            'original_completion': completion}


def run(source, output):
    rows = json.loads(source.read_text(encoding='utf8'))
    if not isinstance(rows, list):
        raise ValueError('expected_list')
    output.mkdir(exist_ok=False)
    counts, reasons, types = Counter(), Counter(), Counter()
    with (output / 'converted.jsonl').open('x', encoding='utf8') as good, \
         (output / 'quarantine.jsonl').open('x', encoding='utf8') as bad:
        for index, row in enumerate(rows, 1):
            try:
                result = convert(row, index)
            except ValueError as exc:
                reason = str(exc)
                reasons[reason] += 1
                bad.write(json.dumps({'source_record_index': index - 1,
                                      'reason': reason, 'approved_for_training': False}) + '\n')
                continue
            good.write(json.dumps(result, ensure_ascii=False) + '\n')
            counts['converted'] += 1
            issues = result['supervision']['issues']
            counts['issues'] += len(issues)
            counts['explicit_edits'] += sum(i['explicit_edit'] for i in issues)
            counts['all_flagged_issues_have_explicit_edits'] += result['supervision']['all_flagged_issues_have_explicit_edits']
            counts['multi_issue_rows'] += len(issues) > 1
            counts['rows_without_issue_tags'] += not issues
            types.update(i['author_type'] for i in issues)
    assert counts['converted'] + sum(reasons.values()) == len(rows)
    summary = {'input_records': len(rows), **counts, 'quarantined': sum(reasons.values()),
               'quarantine_reasons': dict(reasons), 'author_error_types': dict(types),
               'source_url': 'https://huggingface.co/datasets/fava-uw/fava-data/resolve/main/training.json',
               'dataset_card_license': 'CC-BY-4.0; underlying source rights still apply',
               'source_bytes': source.stat().st_size, 'downloaded_evaluation_annotations': False,
               'full_feedback_contract_complete': 0, 'human_gold': False,
               'approved_for_training': 0, 'new_split_allocation': False,
               'model_calls': 0, 'training_started': False,
               'supervised_tokens': None,
               'limitations': ['synthetic author labels, not independently verified',
                              'no per-issue evidence binding or rationale supplied',
                              'no generated Chinese explanations or protected-content labels',
                              'edit projection retains flagged text lacking explicit edits',
                              'no new evaluation split or independence claim']}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), ensure_ascii=False))
