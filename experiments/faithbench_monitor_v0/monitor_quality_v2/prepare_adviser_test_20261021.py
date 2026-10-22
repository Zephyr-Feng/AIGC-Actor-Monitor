"""Freeze a small adviser-facing test using cached development sources; no models."""
from copy import deepcopy
import json
from pathlib import Path

from actor_feedback_bridge import ADAPTER, monitor_messages, read
from feedback_control import prepare
from prepare_feedback_control_run import write
from prepare_selection_unseen import explanations, make

IDS = ('case_020', 'case_021', 'case_022')
CANDIDATE = '/root/monitor-targeted-sft-v1-20261021/run/checkpoint-00012/adapter'
ROOT = Path('data/adviser_test_v1_20261021')


def one_field(source, suffix, path, text):
    row = deepcopy(source)
    row['id'] = source['id'] + '_' + suffix
    target = row['original_action']
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = text
    row['answer'], all_regions = explanations(row['original_action'])
    row['regions'] = [r for r in all_regions if r['path'] == path]
    assert len(row['regions']) == 1
    row['selection_identity_blind'] = True
    row['selection_order_seed'] = 20261121 + IDS.index(source['id'])*100
    row['source_id'] = source['id']
    row['control_kind'] = suffix
    row['human_gold'] = False
    return row


def build():
    ROOT.mkdir(exist_ok=True)
    assert not (ROOT/'sources').exists() and not (ROOT/'monitor_inputs.json').exists()
    make(Path.cwd(), ROOT/'sources', ids=IDS)
    sources = read(ROOT/'sources/inputs.json')
    monitor_rows, actor_templates, references = [], [], []
    for source, unknown in zip(sources, (1536, 8192, 12000)):
        cards = source['cards']
        global_card = next(c for c in cards if isinstance(c['value'],dict) and c['value'].get('tool') == 'global_forensic_analyzer')
        n = global_card['value']['scope']['num_regions_examined']
        gi = next(i for i,x in enumerate(source['original_action']['current_evidence']) if x['source']=='global_forensic_analyzer')
        path = ['current_evidence',gi,'interpretation']
        native = deepcopy(source)
        native.update(id=source['id']+'_native', source_id=source['id'], control_kind='native',
                      selection_identity_blind=True, selection_order_seed=20261121+IDS.index(source['id'])*100, human_gold=False)
        definitions = [
            ('native', None, None, native),
            ('global_error', '全局表征偏离已经证明这张图像由AI生成。', 'revise', None),
            ('known_scope', f'本次全局分析实际检查了{n}个区域。', 'pass', None),
            ('library_unknown', f'该真实参考库的图像总数为{unknown}张。', 'uncertain', None),
        ]
        for kind, quote, expected, row in definitions:
            if row is None:
                row = one_field(source,kind,path,quote)
            scoped = deepcopy(row)
            if quote is not None:
                scoped['answer'] = quote
            messages = monitor_messages(scoped)
            monitor_rows.append(dict(id=row['id'], source_id=source['id'], condition=kind,
                                     messages=messages, expected_status=expected, quote=quote, human_gold=False))
            if kind != 'known_scope':
                actor_templates.append(row)
            references.append(dict(id=row['id'], expected_status=expected, source_card=global_card['id'],
                                   scope_count=n, note='native whole-answer has no automatic semantic gold' if quote is None else 'explicit constructed claim; original evidence unchanged'))
        if source['id']==IDS[0]:
            false_row = one_field(source,'false_count',path,f'本次全局分析实际检查了{n}个区域。')
            quote = false_row['answer'][false_row['regions'][0]['start']:false_row['regions'][0]['end']]
            eid = global_card['id']
            reason = f'实际检查区域只有{n+2}个，原文数量错误。'
            advice = f'本次全局分析实际检查了{n+2}个区域。'
        elif source['id']==IDS[1]:
            li=next(i for i,x in enumerate(source['original_action']['current_evidence']) if x['source']=='local_texture_analyzer')
            false_row=one_field(source,'false_signal',['current_evidence',li,'interpretation'],'局部纹理工具给出合成倾向，但分数强度未校准，不能单独作为最终结论。')
            quote=false_row['answer'][false_row['regions'][0]['start']:false_row['regions'][0]['end']]
            eid=next(c['id'] for c in cards if isinstance(c['value'],dict) and c['value'].get('tool')=='local_texture_analyzer')
            reason='局部纹理工具实际支持真实方向，原文把方向说反了。'
            advice='局部纹理工具给出真实倾向，可据此确认真实来源。'
        else:
            pi=next(i for i,x in enumerate(source['original_action']['current_evidence']) if x['source']=='provenance_inspector')
            false_row=one_field(source,'false_provenance',['current_evidence',pi,'interpretation'],'没有发现可用来源凭据，这一点本身不能证明图像为伪造。')
            quote=false_row['answer'][false_row['regions'][0]['start']:false_row['regions'][0]['end']]
            eid=next(c['id'] for c in cards if isinstance(c['value'],dict) and c['value'].get('tool')=='provenance_inspector')
            reason='没有来源凭据就能证明伪造，应撤回原文保留。'
            advice='未发现来源凭据，因此图像已被证明为伪造。'
        payload={'结论':'revise','问题':[{'状态':'明确错误','回答原文':quote,'证据ID':[eid],'理由':reason,'建议':advice}],'保留':[],'说明':'明确构造错误反馈，用于测试Actor是否依据原始证据抵抗误改。'}
        checked=prepare(false_row['answer'],cards,payload,controlled=True,allowed_ranges=[(r['start'],r['end']) for r in false_row['regions']])
        assert checked['status']=='ready' and len(checked['items'])==1, checked
        false_row['constructed_feedback']=payload
        false_row['feedback_origin']='assistant_constructed_false_control'
        actor_templates.append(false_row)
    assert len(monitor_rows)==12 and len(actor_templates)==12
    write(ROOT/'monitor_inputs.json',monitor_rows)
    write(ROOT/'actor_templates.json',actor_templates)
    write(ROOT/'references.json',references)
    for name,adapter in [('old00373',ADAPTER.as_posix()),('candidate00012',CANDIDATE)]:
        folder=ROOT/name; folder.mkdir()
        write(folder/'inputs.json',monitor_rows)
        write(folder/'authorization.json',dict(approved=True,adapter_enabled=True,adapter_path=adapter,monitor_generations=12,
            training_updates=0,teacher_api_calls=0,new_tool_calls=0,authorization='user requested tests and examples for adviser, GPU is on',
            source_ids=list(IDS),source='existing natural30 development cache; not independent human gold'))
    write(ROOT/'material_review.json',dict(source_ids=list(IDS),training_overlap_current=False,prior_project_exposure=True,
        external_independent_test=False,human_gold=False,license='existing authorized private development cache; original source licenses not newly certified; no redistribution',
        native_normalization='observations program-bound; global direction normalized by existing rule; explanations otherwise preserved',
        unknowns=[1536,8192,12000],maximum_monitor_calls=24,maximum_actor_calls=45,training_updates=0))
    print('Prepared 12 paired Monitor inputs and 12 Actor templates from 3 cached sources.')


if __name__=='__main__':
    build()