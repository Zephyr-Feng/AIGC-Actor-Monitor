"""Record the twelve completed nonblind training-candidate source reviews."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from assemble_feedback import assemble

# The source/answer pairs were read in full; these are assistant references, not human gold.
ACCEPTED={
 '5108':{'quote':"The governor cited a rise in fentanyl deaths and seizures in her state as a reason for withdrawing support",
   'refs':['E001'],'reason':'来源把毒品危机作为支援边境的背景，并明确引述仍愿继续提供帮助；没有把这些数据列为撤回支持的理由。结束当次人员派遣不能改写成因毒品增加而撤回支持。',
   'fix':'撤回这一因果归因，改为本次派遣人员已返回、州长仍表示愿意在需要时提供帮助；保留此前派遣100名人员和30名公共安全官员的事实。',
   'keep':'Iowa had previously deployed 100 personnel and 30 Public Safety Officers to the border.','keep_refs':['E001']},
 '2271':{'quote':'20 million lawful crossings','refs':['E001'],
   'reason':'报道引述的是去年3000万次合法通行；20%描述区域贸易占比，不能换成2000万次通行。',
   'fix':'把2000万次改为3000万次，保留去年及原引述归属，不改变贸易比例等其他不同指标。',
   'keep':'American investment is returning to the city','keep_refs':['E001']},
 '1886':{'quote':'in a South Korean supermarket','refs':['E001'],
   'reason':'来源说Bourdain到Anderson Cooper的厨房烹饪；韩国超市出现在配料购买说明中，不是这次烹饪地点。',
   'fix':'把这处地点改为Anderson Cooper的厨房；节目首播和厨房访问没有被明确说成同一事件，不额外合并时间。',
   'keep':'One popular ingredient in this type of stew is canned Spam.','keep_refs':['E001']},
 '15452':{'quote':'or every other day if they play 30 minutes to an hour every other day.','refs':['E002'],
   'reason':'passage1将隔天弹30至60分钟对应的换弦间隔写为6至8周。回答把演奏频率放到了换弦间隔位置，不能与每天弹奏对应的4至6周混用。',
   'fix':'明确改为：按passage1，隔天弹30至60分钟时每6至8周换弦；其他段落的建议分别保留出处，不强称所有来源完全一致。',
   'keep':'professionals may change their strings more frequently, for every gig.','keep_refs':['E002']},
 '13013':{'quote':'other conditions caused by viruses.','refs':['E001'],
   'reason':'按passage3，这个例子被放在可传播疾病一类，回答却把它列为不可传播疾病，颠倒了所给材料中的归类。这里只核来源表述，不扩展成新的医学结论。',
   'fix':'从不可传播疾病的例子列表中移除该项，若保留则按passage3放在可传播一类；呼吸系统例子还须保留来源的non-infectious限定。',
   'keep':'communicable diseases can be transmitted from one person to another, while non-communicable diseases cannot.','keep_refs':['E001']},
 '6435':{'quote':'free WiFi','refs':['E010'],'reason':'WiFi字段明确为paid，三条评论也没有给免费WiFi的相反说明；回答将付费改成免费。',
   'fix':'把免费WiFi改为付费WiFi，只改该服务收费性质，不改变总体3.5星评分等有据事实。',
   'keep':'With a rating of 3.5 stars','keep_refs':['E007']},
 '9357':{'quote':'offers outdoor seating','refs':['E018'],'reason':'OutdoorSeating=false，所给评论未报告相反的户外座位信息；这项肯定陈述与字段相反。',
   'fix':'撤回提供户外座位的陈述，按资料说明不提供；免费WiFi字段为free，应保留这一不同服务事实。',
   'keep':'free WiFi','keep_refs':['E030']},
 '11846':{'quote':'Monday through Sunday from 12:00 pm to 2:00 am.','refs':['E035','E003','E039','E008','E028','E025','E001'],
   'reason':'周二、周三16点开门，周四14点，周五至周日12点，不能整周概括为12点开门。周二至周日2点关门有依据，不应一并否定。周一记录为0:0-0:0，未在此擅定该编码语义。',
   'fix':'按各日分别列开门时间，保留周二至周日2点关门；周一按原记录及明确数据约定处理，不能写成12点开门。',
   'keep':'The bar has outdoor seating, free WiFi, and is good for groups.','keep_refs':['E006','E013','E032']}}

HELD={
 '5030':'据称曾供认不严格排除另一次否认；来源没提供否认，故可能属于无依据而非直接矛盾。须保留allegedly及报道归属，不能改成已证实犯罪。',
 '11993':'totally up to your own judgement不能单独证明避免频繁剪发必然与来源矛盾。原回答更长的损伤/减慢生长因果还缺依据；来源对修剪促生长说法自身不一，先不导入这一标签。',
 '12987':'1/4对应回答新增的芝麻酱配方，passage2的1/2对应花椰菜饭。酱汁具体量无来源，但不能直接拿饭的量替换酱汁量，保留对象/类型争议。',
 '11240':'BusinessParking.lot=false不直接证明附近公共停车场不存在。当前回答的附近停车场缺依据，但作者Conflict类型与停车范围需裁决，不能训练成周边一定无停车场。'}


def run(root):
    selected=json.loads((root/'review_batch01.selection.json').read_text(encoding='utf8'))['ids']
    rows={r['id']:r for r in map(json.loads,(root/'review_candidates.jsonl').read_text(encoding='utf8').splitlines())}
    reviews=[];examples=[]
    for key in selected:
        row=rows[key];number=row['origin'].split(':')[-1]
        review={'candidate_id':key,'group':row['group'],'full_source_read':True,'reviewer':'assistant_nonblind','human_gold':False}
        if number in HELD:
            review.update(status='held_for_adjudication',note=HELD[number],approved_for_training=False)
        else:
            item=ACCEPTED[number];answer=row['input']['待核回答'];cards=row['input']['证据卡']
            assert item['quote'] in answer and item['keep'] in answer
            target={'结论':'revise','问题':[{'状态':'明确错误','回答原文':item['quote'],'证据ID':item['refs'],'理由':item['reason'],'建议':item['fix']}],
                '保留':[{'回答原文':item['keep'],'证据ID':item['keep_refs']}],'说明':'仅对指定主张及明确保留项作来源核查，不宣称全文无其他错误。'}
            assemble(answer,cards,target)
            review.update(status='assistant_reference_prepared',note=item['reason'],approved_for_training=False)
            for mode in ('problem','supported_control'):
                inputs=deepcopy(row['input'])
                inputs['指定主张']=item['quote'] if mode=='problem' else item['keep']
                reference=target if mode=='problem' else {'结论':'pass','问题':[],'保留':[{'回答原文':item['keep'],'证据ID':item['keep_refs']}],
                    '说明':'仅此指定主张有来源依据，不代表全文其他句子均正确。'}
                assemble(answer,cards,reference)
                examples.append({'id':f'{key}:{mode}','group':row['group'],'input':inputs,'target':reference,
                    'provenance':{'origin':row['origin'],'original_author_label':row['human_span_annotation'],
                        'feedback_annotation':'assistant_nonblind_source_review','human_gold':False,'source_read_in_full':True,
                        'scope':'one specified claim; full response retained','approved_for_training':False}})
        reviews.append(review)
    assert len(reviews)==12 and len(examples)==16
    for name,records in (('review_batch01.decisions.jsonl',reviews),('review_batch01.references.jsonl',examples)):
        with (root/name).open('x',encoding='utf8') as stream:
            for row in records:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({'reviewed':12,'reference_source_groups':8,'reference_examples':16,'held':4,'human_gold':False,'approved_for_training':0},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);run(parser.parse_args().root)
