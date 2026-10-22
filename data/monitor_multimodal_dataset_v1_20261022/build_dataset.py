"""Bounded CPU dataset preparation; direct HTTP/files, no model calls or digests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from collections import Counter
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DATASET = 'lmms-lab/llava-critic-113k'
SOURCE = REPO / 'data/monitor_net_gain_sft_v2_20261021/forensic.sources.json'


def save(path, value):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def read_url(url, maximum):
    request = urllib.request.Request(url, headers={'User-Agent': 'MonitorDatasetPreparation/1.0'})
    with urllib.request.urlopen(request, timeout=45) as response:
        value = response.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError('response exceeds frozen size limit')
    return value


def fetch_public():
    assert not (ROOT / 'public_candidates.json').exists()
    card_url = f'https://huggingface.co/datasets/{DATASET}/raw/main/README.md'
    card_path = ROOT / 'raw/public_dataset_card.md'
    card = card_path.read_text(encoding='utf-8') if card_path.exists() else read_url(card_url, 200000).decode('utf-8')
    assert 'license: apache-2.0' in card
    (ROOT / 'raw').mkdir(exist_ok=True)
    if not card_path.exists():
        with card_path.open('x', encoding='utf-8') as stream:
            stream.write(card)
    offsets = [i * 72782 // 16 for i in range(16)]
    contract = dict(stage='candidate_construction_not_training', public_dataset=DATASET,
         config='pointwise', split='train', offsets=offsets, page_length=100,
         max_public_images=512, max_image_bytes=12000000, model_calls=0,
         domain_source_file=str(SOURCE.relative_to(REPO)), domain_sources=11,
         public_label_strength='publisher_GPT4o_not_human_gold',
         excluded_public='Volcano: license unresolved; preference-only datasets not silently converted',
         scope='download public candidates and existing 11 training sources only; no frozen evaluation inputs')
    if (ROOT / 'build_contract.json').exists():
        assert json.loads((ROOT / 'build_contract.json').read_text(encoding='utf-8')) == contract
    else:
        save('build_contract.json', contract)

    def page(offset):
        cached = ROOT / f'raw/page_{offset:05d}.json'
        if cached.exists():
            return json.loads(cached.read_text(encoding='utf-8'))['rows']
        query = urllib.parse.urlencode(dict(dataset=DATASET, config='pointwise', split='train', offset=offset, length=100))
        try:
            data = json.loads(read_url('https://datasets-server.huggingface.co/rows?' + query, 10000000))
        except Exception as exc:
            return [dict(fetch_error=str(exc)[:200], offset=offset)]
        save(f'raw/page_{offset:05d}.json', data)
        return data['rows']

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(page, offsets))
    candidates, quarantine, seen_ids, selected_groups = [], [], set(), set()
    for entry in [row for batch in pages for row in batch]:
        if 'fetch_error' in entry:
            quarantine.append(entry)
            continue
        row = entry['row']
        uid = row['id']
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        parts = uid.split('__')
        if len(parts) < 3 or not isinstance(row.get('image'), dict):
            quarantine.append(dict(id=uid, reason='unrecognized provenance or image'))
            continue
        group = parts[1]
        conversations = row.get('conversations', [])
        if len(conversations) != 2 or [c['from'] for c in conversations] != ['human', 'gpt']:
            quarantine.append(dict(id=uid, reason='unexpected dialogue shape'))
            continue
        prompt, critique = [c['value'] for c in conversations]
        if re.search(r'reference\s*(?:answer|response)\s*:', prompt, re.I):
            quarantine.append(dict(id=uid, reason='reference-answer-conditioned prompt; needs separate task'))
            continue
        if group in selected_groups or len(candidates) >= 512:
            continue
        selected_groups.add(group)
        candidates.append(dict(id=f'public_{len(candidates):04d}', source_dataset=DATASET,
             publisher_id=uid, publisher_row=entry['row_idx'], origin_task=row['source'],
             source_group='llava-critic:' + group, group_basis='publisher_task_item_not_certified_photo_family',
             image='assets/public/' + f'{len(candidates):04d}.png',
             source_image_url=row['image']['src'], original_prompt=prompt, original_feedback=critique,
             label_strength='publisher_GPT4o_not_human_gold', human_gold=False,
             declared_license='apache-2.0; upstream image rights retained',
             split='unassigned', training_eligible=False, review_status='pending_visual_and_target_review'))

    def image(row):
        try:
            payload = read_url(row['source_image_url'], 12000000)
            with Image.open(BytesIO(payload)) as opened:
                opened.load()
                rgb = opened.convert('RGB')
            if min(rgb.size) < 48:
                raise ValueError('image too small')
            output = ROOT / row['image']
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as stream:
                rgb.save(stream, format='PNG')
            row['image_size'] = list(rgb.size)
            # Expiring preview URLs remain only in the raw retrieval receipt.
            row.pop('source_image_url')
            return row, None
        except Exception as exc:
            return None, dict(id=row['publisher_id'], reason='image_download_or_decode', error=str(exc)[:200])

    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(image, candidates))
    candidates = [row for row, error in fetched if row is not None]
    quarantine.extend(error for row, error in fetched if error is not None)
    # Compare decoded content directly. No digest or fingerprint is computed.
    distinct, pixels = [], []
    for row in candidates:
        with Image.open(ROOT / row['image']) as opened:
            size, content = opened.size, opened.tobytes()
        duplicate = next((prior for shape, value, prior in pixels if shape == size and value == content), None)
        if duplicate is not None:
            quarantine.append(dict(id=row['publisher_id'], reason='exact_decoded_image_duplicate', same_as=duplicate))
            continue
        pixels.append((size, content, row['id']))
        distinct.append(row)
    save('public_candidates.json', distinct)
    save('public_quarantine.json', quarantine)
    print(json.dumps(dict(public_candidates=len(distinct), quarantined=len(quarantine),
                         tasks=sorted({r['origin_task'] for r in distinct})), ensure_ascii=False))


def sheets():
    rows = json.loads((ROOT / 'public_candidates.json').read_text(encoding='utf-8'))
    # Fixed, source-spread review order; this is selection for annotation, not evaluation.
    by_task = {}
    for row in rows:
        by_task.setdefault(row['origin_task'], []).append(row)
    selected = []
    while len(selected) < min(32, len(rows)):
        for task in sorted(by_task):
            if by_task[task] and len(selected) < 32:
                selected.append(by_task[task].pop(0))
    save('public_review_queue.json', selected)
    for start in range(0, len(selected), 8):
        canvas = Image.new('RGB', (2000, 1120), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, row in enumerate(selected[start:start + 8]):
            with Image.open(ROOT / row['image']) as source:
                thumb = ImageOps.contain(source, (490, 510))
            x, y = (j % 4) * 500, (j // 4) * 560
            canvas.paste(thumb, (x + (500-thumb.width)//2, y + 35))
            draw.text((x + 8, y + 8), row['id'], fill='black')
        canvas.save(ROOT / f'review_sheet_{start//8:02d}.png')
    print('review queue', len(selected))


def check():
    rows = json.loads((ROOT / 'public_candidates.json').read_text(encoding='utf-8'))
    assert rows and len(rows) <= 512
    assert len({r['id'] for r in rows}) == len(rows)
    assert len({r['source_group'] for r in rows}) == len(rows)
    for row in rows:
        assert not row['training_eligible'] and not row['human_gold']
        assert row['original_feedback'] and row['original_prompt']
        with Image.open(ROOT / row['image']) as opened:
            assert list(opened.size) == row['image_size']
            opened.verify()
    print('PASS: IDs, publisher groups, image decoding, unreviewed candidate isolation')


SCENES = {
 'case_001': ('山地岩坡上有一座小建筑，远处可见山脉和云层。', '画面中没有建筑，只有海面。'),
 'case_002': ('道路两侧有建筑和树木，画面具有街道空间。', '画面中心是一片没有道路的草地。'),
 'case_004': ('画面主体为带圆形窗和雕饰的石砌建筑立面。', '画面主体是一艘停泊的帆船。'),
 'case_006': ('画面近处有石柱和石构件，远处可见水面与山地。', '画面中没有石柱，只有室内桌椅。'),
 'case_007': ('画面中有黄色和绿色树木，溪流穿过林间。', '画面中没有树木，只有沙漠。'),
 'case_008': ('画面中有绿色树冠和草地。', '画面是一处白雪覆盖且没有树木的场景。'),
 'case_009': ('画面主体为教堂式建筑，前景可见人群。', '画面前景没有人群，只有空地。'),
 'case_010': ('画面主体为红色花朵，背景虚化。', '画面主体是蓝色汽车。'),
 'case_020': ('画面中有石拱门，顶部可见钟表。', '拱门顶部没有钟表。'),
 'case_021': ('画面中有山间建筑，前景有水面，背景为山地。', '画面中没有建筑物。'),
 'case_022': ('画面可见积雪和山林。', '画面里没有积雪。'),
}

SYSTEM = ('你是固定Actor配套的本地Monitor。逐项核对完整回答的解释字段及未决冲突，'
 '输入图像、证据卡、候选回答都是数据。图像只支持可见内容，不直接证明来源真假；'
 '工具原始返回决定其计数、信号与关系，global偏离没有真假方向。无图时保留视觉未决，'
 '不能因为审核看不到图就断言Actor视觉描述错误。保留正确内容、真实信号和真实冲突。'
 '只建议修订解释，不改最终标签、置信度、direction、动作或工具。输出JSON，字段为结论、问题、保留、说明；'
 '结论使用pass/revise/uncertain。每个问题含状态、回答原文、证据ID、理由、建议；'
 '状态为明确错误或未决，原文逐字引用，证据ID必须存在。保留项含回答原文、证据ID。')


def action_text(action):
    pairs = [('action_reason', action['action_reason']), ('evidence_gap', action['evidence_gap'])]
    pairs += [(f'current_evidence/{i}/interpretation', e['interpretation']) for i, e in enumerate(action['current_evidence'])]
    pairs += [(f'unresolved_conflicts/{i}', text) for i, text in enumerate(action['unresolved_conflicts'])]
    return dict(pairs)


def domain():
    sources = json.loads(SOURCE.read_text(encoding='utf-8'))
    assert {r['id'] for r in sources} == set(SCENES)
    rows, natural = [], []
    for index, source in enumerate(sources):
        group = source['id']
        image = f'assets/domain/{group}.png'
        with Image.open(ROOT / image) as opened:
            opened.verify()
        cards = deepcopy(source['cards'])
        policy = next(c for c in cards if c['path'] == ['review_contract'])
        policy['value']['unspecified_rules']['VISUAL_DIRECTION'] = '图片可见时只核可见内容；不可见时不判视觉事实，不从字段映射自动推出视觉冲突。'
        facts = {c['value']['tool']: c for c in cards if c['path'] == ['observed_tool_return']}
        global_card = facts['global_forensic_analyzer']
        local_card = facts['local_texture_analyzer']
        comp_card = facts.get('complementary_forensic_analyzer')
        provenance = facts.get('provenance_inspector')
        n = global_card['value']['scope']['num_regions_examined']
        atypical = global_card['value']['observations']['num_atypical_regions']
        local_signal = local_card['value']['signal']
        comp_signal = comp_card['value']['signal'] if comp_card else None
        relation = ('相反' if (local_signal == 'synthetic_like') != (comp_signal == 'fake') else '同向') if comp_card else None
        actual_relation = f'local原始信号为{local_signal}' + (f'，comp为{comp_signal}，二者方向{relation}。' if comp_card else '；未提供comp实际返回。')
        canonical = deepcopy(source['original_action'])
        canonical['action_reason'] = actual_relation + 'global只反映表征偏离，不参与真假方向投票；这些信号不单独证明图像来源。'
        canonical['evidence_gap'] = '原始分数强度并非校准概率，图像来源不能仅凭外观或表征偏离确认。'
        canonical['unresolved_conflicts'] = [actual_relation] if relation == '相反' else []
        for item in canonical['current_evidence']:
            tool = item['source']
            if tool == 'visual':
                item['interpretation'] = SCENES[group][0] + '单凭这些可见内容不能证明拍摄或生成来源。'
            elif tool == 'global_forensic_analyzer':
                item['interpretation'] = f'本次实际检查{n}个区域，其中异常区域{atypical}个；偏离不是伪造概率或来源证明，参考库容量未提供。'
            elif tool in facts:
                value = facts[tool]['value']
                if tool == 'provenance_inspector':
                    item['interpretation'] = '来源返回inconclusive；缺少凭据不能证明图像真实或伪造。'
                else:
                    item['interpretation'] = f"原始signal为{value['signal']}，score为{value['score']}；保留该方向，但强度不是校准置信度，不能单独证明来源。"
        global_index = next(i for i,e in enumerate(canonical['current_evidence']) if e['source'] == 'global_forensic_analyzer')
        local_index = next(i for i,e in enumerate(canonical['current_evidence']) if e['source'] == 'local_texture_analyzer')
        visual_index = next(i for i,e in enumerate(canonical['current_evidence']) if e['source'] == 'visual')

        def record(kind, action, problems, visible=True):
            evidence = deepcopy(cards)
            image_id = f'E{len(evidence)+1:03d}'
            evidence.append(dict(id=image_id, path=['input_image'], value=dict(available=visible, image_id=group)))
            for issue in problems:
                if issue['证据ID'] == ['IMAGE']:
                    issue['证据ID'] = [image_id]
            verdict = 'revise' if any(p['状态']=='明确错误' for p in problems) else 'uncertain' if problems else 'pass'
            target = dict(结论=verdict, 问题=problems,
                          保留=[dict(回答原文=actual_relation, 证据ID=[local_card['id']]+([comp_card['id']] if comp_card else []))]
                               if actual_relation in '\n'.join(action_text(action).values()) else [],
                          说明='逐处修正解释，保留实际工具方向、真实冲突与全部受保护字段。')
            user = dict(证据卡=evidence, 待核回答=action_text(action), 原始完整动作=action,
                        审核范围='审核全部可编辑解释及未决；原始观测作为上下文，不认证最终标签。', 图片可见=visible)
            text = json.dumps(user, ensure_ascii=False)
            messages = [dict(role='system',content=SYSTEM),dict(role='user',content=([dict(type='image',image=image)] if visible else [])+[dict(type='text',text=text)]),
                        dict(role='assistant',content=json.dumps(target,ensure_ascii=False))]
            return dict(id=f'domain_{group}_{kind}',source_group='domain:'+group,origin='existing_allowed_training_source',
                        task='complete_explanation_critique',split='train',human_gold=False,
                        label_strength='assistant_visual_and_evidence_review_not_human_gold',
                        construction='assistant_text_variation_of_answer; original_image_and_observed_tool_returns_unchanged',
                        source_file=str(SOURCE.relative_to(REPO)),image=image if visible else None,
                        messages=messages,target=target,training_eligible=True,kind=kind)

        def problem(text, ids, reason, suggestion, status='明确错误'):
            return dict(状态=status,回答原文=text,证据ID=ids,理由=reason,建议=suggestion)

        rows.append(record('correct_full',deepcopy(canonical),[]))
        action=deepcopy(canonical)
        bad='global表征偏离已证明图像为伪造。'
        action['action_reason'] += bad
        action['current_evidence'][global_index]['interpretation'] = bad
        action['evidence_gap'] = bad
        action['unresolved_conflicts'].append('global的真假方向与其他工具冲突。')
        problems=[problem(text,[global_card['id']],f'{path}把非方向global当作真假证明或方向冲突；应保留其统计局限。','撤回该归因；global不提供真假方向，不影响实际local/comp关系。')
                  for path,text in action_text(action).items() if bad in text or text=='global的真假方向与其他工具冲突。']
        rows.append(record('global_multifield',action,problems))
        action=deepcopy(canonical);wrong=n+2+index%4
        bad=f'本次实际检查{wrong}个区域。';action['current_evidence'][global_index]['interpretation']=bad
        rows.append(record('wrong_count',action,[problem(bad,[global_card['id']],f'scope.num_regions_examined实际为{n}；异常数{atypical}和top区域列表也不能替代检查数。',f'改为本次实际检查{n}个区域。')]))
        action=deepcopy(canonical);capacity=[3072,6144,12288,14336,24576,4096,16384,7168,2048,10240,32768][index]
        bad=f'真实参考库包含{capacity}张图像。';action['current_evidence'][global_index]['interpretation']=bad
        rows.append(record('unknown_capacity',action,[problem(bad,[global_card['id']],'reference只给出类型和距离计算参数，没有提供参考库图像数量。','撤回该数字，说明参考库容量未提供。')]))
        action=deepcopy(canonical);opposite='real_like' if local_signal=='synthetic_like' else 'synthetic_like'
        bad=f'local实际返回{opposite}。';action['current_evidence'][local_index]['interpretation']=bad;action['evidence_gap']=bad
        rows.append(record('signal_multifield',action,[problem(text,[local_card['id']],f'{path}与实际signal={local_signal}相反；未校准不抹去方向。',f'恢复{local_signal}，保留分数和局限。') for path,text in action_text(action).items() if text==bad]))
        action=deepcopy(canonical)
        bad=(f'local为{local_signal}，comp为{comp_signal}，两者方向'+('同向。' if relation=='相反' else '相反。')) if comp_card else 'global与local的真假方向相反。'
        action['evidence_gap']=bad;action['unresolved_conflicts']=[bad]
        ids=[local_card['id'],comp_card['id']] if comp_card else [local_card['id'],global_card['id']]
        rows.append(record('relationship_multifield',action,[problem(text,ids,f'{path}错误绑定实际工具关系；'+actual_relation if comp_card else f'{path}把无方向global当成相反票。',actual_relation+'global不参与方向比较。') for path,text in action_text(action).items() if text==bad]))
        action=deepcopy(canonical)
        bad='未发现来源凭据，因此图像已被证明为伪造。' if provenance else '没有调用来源工具，因此图像已被证明为伪造。'
        action['evidence_gap']=bad
        rows.append(record('absence_proof',action,[problem(bad,[provenance['id']] if provenance else [cards[0]['id']],'来源缺失或未调用不能充当伪造证明。','撤回定假推断，保留来源未知及其他实际信号。')]))
        action=deepcopy(canonical);bad=SCENES[group][1];action['current_evidence'][visual_index]['interpretation']=bad
        rows.append(record('visual_wrong',action,[problem(bad,['IMAGE'],'输入图片可见：'+SCENES[group][0],'改为：'+SCENES[group][0]+'不据此判断图像来源。')]))
        rows.append(record('visual_unavailable',action,[problem(bad,['IMAGE'],'当前图片不可见，工具返回不足以核实这个具体视觉描述。','保留未决；不能因本轮缺图就断言该视觉描述错误。','未决')],visible=False))
        natural.append(dict(id=f'native_{group}',source_group='domain:'+group,image=image,
                            original_action=source['original_action'],original_feedback=source.get('feedback'),
                            training_eligible=False,review_status='pending_complete_native_target_review',
                            reason='保留自然原稿；旧反馈未必覆盖unresolved_conflicts，不自动认证整稿监督。'))
    original_by_group={r['id']:r for r in sources}
    for row in rows:
        user=json.loads(next(v['text'] for v in row['messages'][1]['content'] if v['type']=='text'))
        original=original_by_group[row['source_group'].split(':',1)[1]]
        assert [c for c in user['证据卡'] if c['path']==['observed_tool_return']] == [c for c in original['cards'] if c['path']==['observed_tool_return']]
        text='\n'.join(action_text(user['原始完整动作']).values())
        assert all(p['回答原文'] in text for p in row['target']['问题'])
        assert all(set(p['证据ID']) <= {c['id'] for c in user['证据卡']} for p in row['target']['问题'])
    assert len(rows)==99 and len({r['source_group'] for r in rows})==11
    save('domain_train.json',rows)
    save('domain_native_candidates.json',natural)
    save('domain_review_receipt.json',dict(images_reviewed=11,reviewer='assistant_not_human_gold',
         constructed_rows=99,natural_rows_not_auto_accepted=11,observed_tool_returns_unchanged=True,
         visual_observations_not_certified_as_gold=True,source_exposure='all existing development/training exposed',
         frozen_evaluation_sources_not_used=True))
    print('PASS: 99 source-grouped explanation records / 11 images; natural candidates remain isolated')


def extract_candidate(row):
    prompt = row['original_prompt']
    answer = re.search(r'\[Assistant 2\]\s*(.*?)\s*\[End of Assistant 2\]', prompt, re.S)
    if answer:
        question = re.search(r'\[Question\]\s*(.*?)\s*\[Assistant 1\]', prompt, re.S)
        if not question:
            raise ValueError('question marker missing')
        return question[1], answer[1]
    if row['origin_task'] == 'svit-detail_description':
        return 'Describe the image.', prompt.split('Text Caption:',1)[1].split('\nFrom 0',1)[0].strip()
    if '### LMM Response to Evaluate' in prompt:
        return (prompt.rsplit('### Question',1)[1].split('### Standard',1)[0].strip(),
                prompt.rsplit('### LMM Response to Evaluate',1)[1].strip())
    if row['origin_task'] == 'comvint':
        cells=re.split(r'\s+\|\s*',prompt.strip().splitlines()[-1])
        if len(cells)!=4 or not cells[0] or not cells[2]:
            raise ValueError('unexpected final question/reference/prediction table row')
        return cells[0],cells[2]
    raise ValueError('unreviewed extraction format')


def public_adapt():
    candidates = json.loads((ROOT/'public_candidates.json').read_text(encoding='utf-8'))
    queue = json.loads((ROOT/'visual_review_queue.json').read_text(encoding='utf-8'))
    annotations = json.loads((ROOT/'visual_annotations.json').read_text(encoding='utf-8'))
    assert len(queue)==len(annotations)==64 and {r['id'] for r in queue}==set(annotations)
    split_by_group, counts = {}, Counter()
    for row in queue:
        counts[row['origin_task']] += 1
        split_by_group[row['source_group']] = 'development' if counts[row['origin_task']] % 5 == 0 else 'train'
    rows = []

    def record(row, kind, answer, target, visible=True, construction='assistant_control_from_visually_reviewed_image', question='核对完整候选回答的事实依据。'):
        evidence = [dict(id='E001',path=['input_image'],value=dict(available=visible,image_id=row['id'])),
                    dict(id='E002',path=['supplied_context'],value=dict(provenance_credentials_provided=False,
                         scope='只有图片和问题；未提供拍摄、生成、来源凭据、取证工具或运行状态数据。'))]
        material = dict(问题=question,证据卡=evidence,待核回答=answer,图片可见=visible,
                        审核范围='逐处核对事实与未决；不因缺少额外细节就判明确错误，不编造取证工具或来源标签。')
        content = ([dict(type='image',image=row['image'])] if visible else [])+[dict(type='text',text=json.dumps(material,ensure_ascii=False))]
        return dict(id=f"adapted_{row['id']}_{kind}",source_group=row['source_group'],
                    source_dataset=DATASET,publisher_id=row['publisher_id'],publisher_row=row['publisher_row'],
                    task='complete_visual_answer_critique',kind=kind,split=split_by_group[row['source_group']],
                    image=row['image'] if visible else None,human_gold=False,
                    label_strength='assistant_visual_review_not_human_gold',construction=construction,
                    declared_license=row['declared_license'],training_eligible=True,
                    messages=[dict(role='system',content=SYSTEM),dict(role='user',content=content),dict(role='assistant',content=json.dumps(target,ensure_ascii=False))],target=target)

    def issue(text, reason, suggestion, status='明确错误', ids=None):
        return dict(状态=status,回答原文=text,证据ID=ids or ['E001'],理由=reason,建议=suggestion)

    def target(verdict, issues, retained=None):
        return dict(结论=verdict,问题=issues,保留=retained or [],说明='依据实际可见内容逐处修正，不能将视觉外观当作来源证明；未提供的事实保留未知。')

    for row in queue:
        good,bad=annotations[row['id']]
        answer=dict(action_reason=good,visual_interpretation=good,evidence_gap='没有提供来源凭据，无法仅凭外观确认拍摄或生成来源。',unresolved_conflicts=[])
        rows.append(record(row,'correct_full',deepcopy(answer),target('pass',[],[dict(回答原文=good,证据ID=['E001'])])))
        wrong=deepcopy(answer)
        for key in ('action_reason','visual_interpretation','evidence_gap'):wrong[key]=bad
        issues=[issue(bad,f'{key}与图片可见内容矛盾；'+good,'改为：'+good) for key in ('action_reason','visual_interpretation','evidence_gap')]
        rows.append(record(row,'visual_multifield',deepcopy(wrong),target('revise',issues)))
        issues=[issue(bad,f'{key}涉及具体视觉事实，但当前未提供图片，不能用缺图证明其错误。','保留未决，待实际图片可用后核对。','未决') for key in ('action_reason','visual_interpretation','evidence_gap')]
        rows.append(record(row,'visual_unavailable',deepcopy(wrong),target('uncertain',issues),visible=False))
        provenance=deepcopy(answer);proof='这张图已被证明是真实拍摄的。';provenance['evidence_gap']=proof
        rows.append(record(row,'source_unknown',provenance,target('revise',[issue(proof,'输入没有来源凭据，图片外观不能提供该来源证明。','撤回已证明的断言，说明来源无法确认。',ids=['E002'])],[dict(回答原文=good,证据ID=['E001'])])))

    accepted = {'public_0205','public_0206','public_0207','public_0208','public_0209','public_0210',
                'public_0257','public_0258','public_0259','public_0260','public_0261','public_0262',
                'public_0231','public_0232','public_0003','public_0456'}
    notes=[]
    reviewed=json.loads((ROOT/'public_review_queue.json').read_text(encoding='utf-8'))
    for row in reviewed:
        uid=row['id']
        if uid not in accepted:
            reason=('评分与解释互相矛盾，不能原样作为监督。' if uid=='public_0459' else
                    '开放推理或建议任务，不作为本批客观视觉纠错监督。' if row['origin_task']=='llava-reasoning' else
                    '原候选多处细节、人物计数或身份/物种判定尚不能完整可靠核实；原标签隔离。')
            notes.append(dict(id=uid,original_feedback_accepted=False,reason=reason,
                              image_may_support_separately_annotated_simple_controls=True))
            continue
        question,answer=extract_candidate(row)
        if uid=='public_0205':
            output=target('revise',[issue(answer,'候选为数字串，未回答图片中的引语问题；图片实际有清晰英文句子。','根据图片文字回答：There is only one happiness in this life, to love and be loved.')])
        elif uid=='public_0207':
            output=target('revise',[issue(answer,'问题要求读取海报议题，候选却编写静态图不支持的车辆运动和等待故事，也未回答议题。','按图中文字回答Housing Instability、COVID-19 in Prisons、Burning Bush Brewery a Year Later；删除无据事件叙述。')])
        elif uid=='public_0232':
            quote='There are also two other animals nearby'
            output=target('revise',[issue(quote,'画面可见两只斑马，而不是一只斑马之外另有两只动物。','改为画面可见两只斑马，不臆测额外动物或观察者。')])
        elif uid=='public_0003':
            quote='Some of them have their engines running and others are not in operation yet.'
            output=target('uncertain',[issue(quote,'静态图片能确认停机坪上的飞机，不能核实这些发动机的实际运行状态。','撤回确定的运行状态描述，说明图片不足以确认。','未决')],
                          [dict(回答原文='In this image, there are several airplanes parked on an airport tarmac.',证据ID=['E001'])])
        elif uid=='public_0456':
            output=target('revise',[issue(answer,'图片中的人物倚靠墙面站立，一条腿弯起，并非坐在长椅上。','改为人物靠墙站立；不把弯腿姿势说成坐在长椅上。')])
        else:
            output=target('pass',[],[dict(回答原文=answer,证据ID=['E001'])])
        rows.append(record(row,'native_adapted',answer,output,construction='original_candidate_preserved; assistant_replaced_publisher_rubric_and_reviewed_target',question=question))
        notes.append(dict(id=uid,original_feedback_accepted=False,adapted_target_accepted=True,
                          reason='重新按图片与问题审核；移除评分、参考答案、Assistant1必正确假设；简短不等于事实错误。'))
    assert len(rows)==272
    for row in rows:
        user=json.loads(next(v['text'] for v in row['messages'][1]['content'] if v['type']=='text'))
        text=json.dumps(user['待核回答'],ensure_ascii=False) if not isinstance(user['待核回答'],str) else user['待核回答']
        assert all(issue['回答原文'] in text for issue in row['target']['问题'])
        assert 'Standard Human-Generated Answer' not in json.dumps(user) and '[Assistant 1]' not in json.dumps(user)
    save('public_adapted.json',rows)
    save('public_review_decisions.json',notes)
    save('source_split.json',dict(public_groups=split_by_group,domain_groups='all 11 existing exposed groups remain train',
          method='within origin task, every fifth reviewed publisher group is development; no model-based selection',
          limitations='exact decoded duplicates excluded; near-duplicate photo-family independence not certified; development is not independent gold'))
    print('PASS: 256 visually grounded controls + 16 adapted original candidates; publisher rubric excluded')


def package():
    domain_rows=json.loads((ROOT/'domain_train.json').read_text(encoding='utf-8'))
    public_rows=json.loads((ROOT/'public_adapted.json').read_text(encoding='utf-8'))
    rows=domain_rows+public_rows
    train=[r for r in rows if r['split']=='train']
    development=[r for r in rows if r['split']=='development']
    assert not {r['source_group'] for r in train}&{r['source_group'] for r in development}
    assert len(rows)==len({r['id'] for r in rows})==371
    for row in rows:
        assert row['human_gold'] is False and row['training_eligible']
        target=json.loads(row['messages'][-1]['content'])
        assert set(target)=={'结论','问题','保留','说明'} and target==row['target']
        assert target['结论'] in ('pass','revise','uncertain')
        content=row['messages'][1]['content']
        images=[p['image'] for p in content if p['type']=='image']
        assert len(images)==(0 if row['image'] is None else 1)
        for image in images:
            path=(ROOT/image).resolve();assert path.is_relative_to(ROOT.resolve())
            with Image.open(path) as opened:opened.verify()
        user=json.loads(next(p['text'] for p in content if p['type']=='text'))
        ids={c['id'] for c in user['证据卡']}
        assert all(set(p['证据ID'])<=ids for p in target['问题']+target['保留'])
        if target['结论']=='pass':assert not target['问题']
        if target['结论']=='uncertain':assert target['问题'] and all(p['状态']=='未决' for p in target['问题'])
    save('train.candidate.json',train)
    save('development.candidate.json',development)
    summary=dict(status='dataset_candidate_not_model_qualified',rows=len(rows),train_rows=len(train),
                 development_rows=len(development),source_groups=len({r['source_group'] for r in rows}),
                 train_source_groups=len({r['source_group'] for r in train}),development_source_groups=len({r['source_group'] for r in development}),
                 domain_rows=len(domain_rows),domain_sources=11,public_adapted_rows=len(public_rows),public_reviewed_images=64,
                 public_original_candidates_adapted=16,public_constructed_controls=256,
                 native_domain_candidates_pending=11,public_pool_rows=len(json.loads((ROOT/'public_candidates.json').read_text(encoding='utf-8'))),
                 targets=dict(Counter(r['target']['结论'] for r in rows)),
                 train_targets=dict(Counter(r['target']['结论'] for r in train)),development_targets=dict(Counter(r['target']['结论'] for r in development)),
                 kinds=dict(Counter(r['kind'] for r in rows)),
                 images_in_messages=sum(r['image'] is not None for r in rows),image_absent_rows=sum(r['image'] is None for r in rows),
                 max_message_characters=max(len(json.dumps(r['messages'],ensure_ascii=False)) for r in rows),
                 native_tokenizer_length_checked=False,all_labels_assistant_or_publisher_not_human_gold=True,
                 model_calls=0,training_updates=0,teacher_api_calls=0,new_tool_calls=0,
                 source_file_bytes=sum(p.stat().st_size for p in ROOT.rglob('*.png')),
                 intended_next='native multimodal processor preflight and bounded training design; no automatic execution')
    save('summary.json',summary)
    save('validation.json',dict(passed=True,checks=['record IDs unique','train/development source groups disjoint',
         'image files decode','four-field targets and evidence IDs valid','unknown and pass states consistent',
         'domain original tool returns unchanged','no model generation or training','raw public candidates excluded from train'],
         not_certified=['human gold','independent evaluation','near-duplicate source families','native tokenizer lengths','semantic benefit']))
    print(json.dumps(summary,ensure_ascii=False))


def finish():
    sources=json.loads(SOURCE.read_text(encoding='utf-8'))
    specs=json.loads((ROOT/'native_review_spec.json').read_text(encoding='utf-8'))
    controls=json.loads((ROOT/'domain_train.json').read_text(encoding='utf-8'))
    native=[]
    for source in sources:
        group=source['id']; action=source['original_action']; texts=action_text(action)
        row=deepcopy(next(r for r in controls if r['id']==f'domain_{group}_correct_full'))
        user=json.loads(next(c['text'] for c in row['messages'][1]['content'] if c['type']=='text'))
        user['原始完整动作']=deepcopy(action);user['待核回答']=texts
        facts={c['value']['tool']:c for c in source['cards'] if c['path']==['observed_tool_return']}
        task=next(c for c in source['cards'] if c['path']==['task_state'])
        relation=next(r for r in controls if r['id']==f'domain_{group}_correct_full')['target']['保留'][0]['回答原文']
        issues=[];flagged=set()
        for kind,paths in specs[group].items():
            for path in paths:
                assert path in texts;flagged.add(path)
                if kind=='global_relation':
                    ids=[c['id'] for c in facts.values() if c['value']['tool']!='provenance_inspector']
                    status='明确错误';reason=path+'将global当作真假方向或方向冲突，或扩大了冲突范围；global没有真假方向。'+relation
                    suggestion='撤回这处global方向归因；'+relation+'保留实际冲突和来源未知。'
                elif kind=='budget':
                    ids=[task['id']];status='明确错误'
                    reason=f"{path}称所有可用工具均已调用，但实际只调用{len(task['value']['used_tools'])}项、仍有{task['value']['remaining_calls']}次额度；提供规则也未规定此时必须STOP。"
                    suggestion='按实际已调用工具和剩余额度说明；不据此强制增调工具或修改动作。'
                elif kind=='confidence':
                    ids=[facts[t]['id'] for t in ('local_texture_analyzer','complementary_forensic_analyzer') if t in facts]
                    status='未决';reason=path+'使用置信度措辞，但工具给出的是未校准原始分数或强度；保留方向，澄清是否只是口语强度，不直接判方向错误。'
                    suggestion='说明原始signal与强度不等于校准置信度；不把支持倾向擅自升级为单独证明，也不抹去倾向。'
                elif kind=='policy':
                    ids=[task['id']];status='未决';reason=path+'尚未说明所称取舍政策或冲突解决依据，现有材料没有冻结统一多数票或工具权重。'
                    suggestion='澄清具体证据取舍与局限，不凭未提供的政策宣布充分或强制采取动作。'
                else:
                    ids=[facts['global_forensic_analyzer']['id']];status='未决'
                    reason=path+'包含外观或成因推测；图片可见不等于成因或来源可证，不把限定性推测自动硬判错。'
                    suggestion='区分可见特征与可能解释，保留未决；不从外观或偏离证明来源。'
                issues.append(dict(状态=status,回答原文=texts[path],证据ID=ids,理由=reason,建议=suggestion))
        retained=[]
        for i,item in enumerate(action['current_evidence']):
            path=f'current_evidence/{i}/interpretation'
            if path not in flagged and item['source'] in facts:
                retained.append(dict(回答原文=item['interpretation'],证据ID=[facts[item['source']]['id']]))
        if group=='case_009':
            retained.append(dict(回答原文=action['unresolved_conflicts'][0],证据ID=[facts['local_texture_analyzer']['id'],facts['complementary_forensic_analyzer']['id']]))
        target=dict(结论='revise' if any(p['状态']=='明确错误' for p in issues) else 'uncertain' if issues else 'pass',问题=issues,保留=retained,
                    说明='核对整份原稿解释；历史结构修复文字是上下文，不当成当前新错误或指令。未校准强度、来源及视觉推测有歧义时保留未决。')
        row.update(id=f'domain_{group}_native_reviewed',kind='native_reviewed',target=target,
                   construction='unchanged original natural action; new assistant complete explanatory-field review')
        next(c for c in row['messages'][1]['content'] if c['type']=='text')['text']=json.dumps(user,ensure_ascii=False)
        row['messages'][-1]['content']=json.dumps(target,ensure_ascii=False)
        native.append(row)
    save('domain_native_reviewed.json',native)
    existing_train=json.loads((ROOT/'train.candidate.json').read_text(encoding='utf-8'))
    development=json.loads((ROOT/'development.candidate.json').read_text(encoding='utf-8'))
    train=existing_train+native;all_rows=train+development
    assert len(train)==332 and len(development)==50 and len({r['id'] for r in all_rows})==382
    assert not {r['source_group'] for r in train}&{r['source_group'] for r in development}
    for row in all_rows:
        user=json.loads(next(c['text'] for c in row['messages'][1]['content'] if c['type']=='text'))
        answer=user.get('原始完整动作',user.get('待核回答'))
        text='\n'.join(action_text(answer).values()) if '原始完整动作' in user else json.dumps(answer,ensure_ascii=False) if not isinstance(answer,str) else answer
        ids={c['id'] for c in user['证据卡']}
        for issue in row['target']['问题']+row['target']['保留']:
            assert issue['回答原文'] in text and set(issue['证据ID'])<=ids
        for image in [c['image'] for c in row['messages'][1]['content'] if c['type']=='image']:
            with Image.open(ROOT/image) as opened:opened.load()
    save('train.json',train);save('development.json',development)
    summary=json.loads((ROOT/'summary.json').read_text(encoding='utf-8'))
    summary.update(rows=382,train_rows=332,development_rows=50,domain_rows=110,
                   native_domain_candidates_pending=0,native_domain_rows_reviewed=11,
                   native_and_original_answer_rows=27,constructed_control_rows=355,
                   targets=dict(Counter(r['target']['结论'] for r in all_rows)),
                   train_targets=dict(Counter(r['target']['结论'] for r in train)),
                   kinds=dict(Counter(r['kind'] for r in all_rows)),
                   images_in_messages=sum(r['image'] is not None for r in all_rows),
                   final_files=['train.json','development.json'],
                   native_candidates_receipt='domain_native_candidates.json was the pre-review snapshot; superseded by domain_native_reviewed.json')
    save('summary.final.json',summary)
    save('validation.final.json',dict(passed=True,rows=382,train_rows=332,development_rows=50,
         checks=['image decoding','exact quotes and evidence IDs','source split isolation','all final targets use four-field contract'],
         native_review='11 originals reviewed; historical structural notes not misclassified; ambiguities retained',
         limitations=['assistant review not human gold','355 controls not independent natural examples','no native tokenizer or model preflight','no source-family independence certification']))
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'fetch': fetch_public, 'sheets': sheets, 'check': check, 'domain':domain,
     'adapt':public_adapt,'package':package,'finish':finish}[sys.argv[1]]()
