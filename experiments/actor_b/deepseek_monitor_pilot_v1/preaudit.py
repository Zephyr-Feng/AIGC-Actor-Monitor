"""Assistant preaudit of fixed historical nodes; never sent to either model."""
from prepare import PRIVATE, load, dump, canonical_hash

# These are reviewed claims, not a keyword classifier or independent gold.
NOTES = {
 'blind_001': ('error','检测到3个高偏离区域','top-3展示不等于3个阈上异常，实际1/6；过曝/对象自述不能归为工具发现。保留local real_like 0.088203及未校准局限。'),
 'blind_003': ('error','结论高度一致','全局非方向偏离被写fake，来源缺失又并入一致支持；保留local synthetic_like及误报/未校准，不指定最终标签。'),
 'blind_006': ('error','支持图像为合成','action_reason给非方向全局fake支持，与本条direction inconclusive和局限不一致；保留local信号，须解释高置信度与局限。'),
 'blind_008': ('error','全局表征偏离与局部/互补证据存在矛盾','非方向全局不是real方向工具的反证；预算0不能继续，保留两真实方向信号与局限，不虚构新工具。'),
 'blind_010': ('error','需继续取证','raw STOP/null非法，语义说继续却STOP；全局未支持fake不等于反对local，保留local与误报局限。'),
 'blind_012': ('error','但未达校准阈值，证据权重不足','synthetic score低于fake阈值对应real，不是real未通过；非方向全局被当方向冲突。原理由复制结构错误文本。'),
 'blind_015': ('error','与全局表征偏离证据一致','非方向全局被并入合成一致支持，局部强度未校准且可能误报；图块对象归因须区分视觉。'),
 'blind_016': ('error','无新工具可用','仍有互补工具且预算1；来源缺失不是local反证，缺乏佐证与真正方向冲突须区分；保留local fake方向和局限。'),
 'blind_018': ('error','且指向一致','全局direction fake与工具不判来源冲突，元数据/非方向证据不能合称一致fake。保留local数值及局限。'),
 'blind_019': ('reasonable','互补模型同样指向 fake 信号','终态两方向工具一致，global保持非方向；历史曾错称global/local冲突须单列，终态未要求强制补证据。强度不是概率。'),
 'blind_020': ('error','无明确指向 real 或 fake','raw final inconclusive非法；弱real_like确有方向但不等于决定性证据，不能说完全无方向；保留其低强度和不确定性。'),
 'blind_026': ('unassessable','但需确认是否为后期处理而非AI生成','字段global保持非方向，reason综合可能赋支持但表述未完全明确；对象归因仅视觉未核实，单local最终判定的充分性/局限待审，不强判真值。'),
 'blind_027': ('error','均指向合成','global direction fake及一致综合超工具范围；88.9%是8/9阈上异常，并不由median/max得8个都100。保留local原信号。'),
 'blind_030': ('error','均指向合成图像','global赋fake方向且与local合称双重支持，偏离不证明合成。保留local synthetic_like及局限。'),
 'blind_040': ('unassessable','所有证据均无法确定','弱real_like被概括无指向、global64.5被称显著而阈上0；可区分强度弱与无方向，对象定位无像素不能确认；低置信STOP不因预算尚有即强制继续。'),
 'blind_043': ('error','支持图像为真实','低全局偏离不提供real方向，current_evidence real错误；保留local real_like及中等/未校准。'),
 'blind_048': ('error','视觉与局部纹理证据冲突','视觉无明显伪影不等于real反证，复制结构失败提示不能作为行动理由；保留local和全局非方向/来源未决。'),
 'blind_050': ('unassessable','已获得高置信度合成倾向证据','global保持非方向、来源未决，local方向真实但最终high和单工具充分性未说明误报/未校准；不把high单独等同概率虚构，保留待审。'),
 'blind_053': ('error','高置信度支持真实','真实local/互补相反方向确有冲突，应保留；互补强度不等于校准概率，STOP fake理由未解释取舍；历史visual未决当反方向、global当一致支持须修复。'),
 'blind_056': ('error','缺乏明确的 real/fake 信号','local synthetic_like虽弱确有方向，global不能形成反方向冲突；R1-R3是3展示非9检查全部，STOP/null confidence原parser接受须保持。'),
}


def main():
    packets = load(PRIVATE/'monitor_packets.json')
    assert set(NOTES) == set(packets)
    rows = {}
    for cid,(state,quote,note) in NOTES.items():
        packet = packets[cid]
        terminal = packet['current_raw_stop']
        if quote not in terminal:
            assert quote in str(packet['trajectory']), cid
        observations = [s['tool_observation'] for s in packet['trajectory']['steps'] if s.get('tool_observation')]
        rows[cid] = dict(state=state,actor_quote=quote,assessment=note,
                         evidence=[{'tool':o['tool'],'limitations':o['limitations'],
                                    'facts':{k:o[k] for k in ['score','signal','strength','observations','scope'] if k in o}} for o in observations],
                         packet_sha256=canonical_hash(packet))
    dump(PRIVATE/'preaudit.json',{'reviewer':'same assistant; development assessment, not independent gold','gt_read':False,
         'criteria':['逐步只用当时返回','工具事实与视觉自述分开','方向/综合/伪冲突/预算/接口','真实方向与误报校准局限保留','置信度变化不是修复本身'],
         'cases':rows})
    print('20 preaudit entries saved; quotes verified; no model requests')


if __name__ == '__main__':
    main()
