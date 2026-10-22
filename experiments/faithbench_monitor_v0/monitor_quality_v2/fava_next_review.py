"""Persist the bounded assistant review; these judgments are not human gold."""
import json
from pathlib import Path
from fava_trial import readl, write
from prepare_fava_next import OUT, ROOT, write_rows

# Reviewed with all supplied reference cards; quoted fragments keep the record small.
REVIEWS = [
    (['定位错误', '修正措辞扩大'], ['E001'], 'butterfly→backstroke有据；no→significant恢复变化方向，但significant程度未明确给出。', '漏掉butterfly；时间规则整句修正方向合理。', True, 'E001直接支持全部核心事实。'),
    (['定位错误', '漏检', '合理替代删除'], ['E002', 'E005'], '改1950s和DC正确，漏第二个年代1930s→1940s，结果会成为1930s-1930s；删负面遗产句可消除该断言。', '漏年代及DC；遗产句改为肯定有长期角色影响支持。', False, '含so valuable与undoubtedly等评价，保守不作为无错控制。'),
    (['定位错误', '必要删除'], ['E001', 'E002', 'E003', 'E004', 'E005'], '删除Groovy Beat舞步创作者断言有助消除无据内容；各卡均无该支持。', '对无据舞步句作原样替换，未解决问题。', False, '余留highly regarded与remembered by many评价无法直接核验。'),
    (['定位错误', '必要删除', '来源冲突'], ['E001', 'E002', 'E003'], '删除无据Golden Echidna奖；俱乐部E001与E002/E003不同，时间未对齐。', '把无据奖改为Golden Boot仍无据。', False, '俱乐部当前归属存在跨卡冲突，排除。'),
    (['定位错误', '错误替换'], ['E001', 'E002', 'E003'], '删除餐具品牌/市长、改comedian/created合理；erased→directed缺少该剧导演角色证据，E003明确写written。', '市长改成E001另一位David Lawrence的电台主持，发生人物错配。', True, '作者修正的职业、Seinfeld及该剧创作/写作均有E002/E003支持。'),
    (['定位错误', '内容修正合理'], ['E002', 'E003'], 'China→Japan、December→November、single→multi及删1990均有据；与作者片段边界不同但内容一致。', '漏China；拆成多条删除与重复The引用导致不能安全应用。', True, '作者修正后的名称、发行时间、玩法及客串均有据。'),
    (['定位错误', '替换后重复词', '作者修正质量问题'], ['E001', 'E002', 'E004'], 'not→the形成It was the the site，语法错误；应删除not。作者删整句会丢失有据事实并留下孤立句点。', '整句去not的语义修正合理。', False, '作者删除使句点残留，暂不作为干净控制。'),
    (['定位错误', '漏检', '错误替换', '替换后重复词'], ['E002', 'E005'], '漏continent；absence→presence违反无国教证据，never→received重复received；has remained比has disappeared好但未恢复作者emerged。', 'JSON尾部多反引号，仅改Islam→Vodou也不支持最广宗教。', True, '作者修正的country、Vodou及无国教/优待关系由E002/E005支持。'),
    (['定位错误', '漏检', '替换后病句'], ['E001', 'E002', 'E003'], '删文化组织句合理；漏disintegration；completely→the same会形成a the same different，仍未修复目的关系。', '漏文化组织句与disintegration；尾句较大范围改same方向合理。', True, '1836/1948/1953/1966及原亲教会目的有E002/E003支持。'),
    (['定位错误', '合理替代删除', '作者残留标点'], ['E002', 'E003', 'E005'], '删职业蓝调乐手整句合理；来源仅提圣乐创作和音乐研究，不能推出职业蓝调乐手。模型包含句号而作者不含，严格匹配会惩罚。', '只调整King Jr标点，漏主要问题。', False, '作者修正留孤立句点；不凑控制数量。'),
    (['定位错误', '合理替代修正', '作者修正质量问题', '来源冲突'], ['E001', 'E003', 'E004', 'E005'], 'created/protagonist及删名言合理；banned→produced by比作者were banned→were produced更通顺；1965/1966跨卡不一。', '漏antagonist，替换为另一条无据名言。', False, '作者修正缺by，且年份跨卡冲突。'),
    (['定位错误', '合理替代措辞', '作者漏标疑点'], ['E001', 'E004', 'E005'], '删Night Ape、unimportant→significant方向合理；但回答称资料未提供历史，E001/E004实际有历史事件，作者未标。', '只改unimportant，漏Night Ape和未提供历史断言。', False, '作者修正仍声称没有历史信息，与参考不符。'),
    (['定位错误', '内容修正合理'], ['E004', 'E005'], 'enabling及删除无据发明者/1969、删除否认多处控制句均合理。', '把无据发明者句替换为另一个错误否定句，保留原矛盾。', True, '作者修正的控制方式、应用地点及便利性由E004/E005支持。'),
    (['定位错误', '错误否定残留', '无效编辑', '作者修正质量问题'], ['E001', 'E003'], 'closed→opened后does not仍在，反而否定已知机理；does→does无效；modify→transform不必要。作者删除主语后留In organic chemistry, .。', '也保留does not，仅改ring-opened仍错误。', False, '作者删除主语及谓语导致残句，不作为控制。'),
    (['定位错误', '合理替代删除', '信息损失'], ['E001', 'E002', 'E005'], '删除Anubis与宗教集权目的句合理；删整个Contrary to句可消错但损失有据历史背景，不如Prior to最小修正。', '把Anubis改为民法来源有E002依据，但漏末句错误目的和Contrary to关系。', True, '作者修正的创立、司法冲突、苏伊士与棉花贸易均有E001/E005支持。'),
    (['定位错误', '引用歧义', '替换后残句', '作者漏标疑点'], ['E001', 'E002', 'E004'], 'Spain出现两次，不能唯一定位；删除These fossils, including claws and teeth后留下, were found残句；作者还删除本来有据的Portugal对照句。', 'modern-day Spain唯一且改Portugal有据，但漏骨骼类型及recent discovery时间问题。', False, 'recent discovery无时间基准，参考提1987/1999；不视作确认干净。'),
]


def main():
    original = readl(ROOT/'final_eval_373_20261019/development_pool.tokens.jsonl')
    candidates = readl(OUT/'clean.candidates16.jsonl')
    records, accepted = [], []
    for row, candidate, (tags, evidence, after_note, before_note, clean, clean_note) in zip(original, candidates, REVIEWS, strict=True):
        records.append({'id': row['id'], 'group': row['group'], 'tags': tags, 'evidence_ids': evidence,
                        'after_note': after_note, 'before_note': before_note,
                        'before_note_source': 'historical_4090D_before_not_this_run_old00952',
                        'after_note_source': 'historical_5090_after; current original16 raw equality checked separately',
                        'clean_accepted': clean, 'clean_reason': clean_note,
                        'reviewer': 'assistant', 'human_gold': False, 'independent_test': False,
                        'scope': 'all supplied cards and full answer; factual evidence consistency; conservative clean gate'})
        if clean:
            candidate.update(approved_for_evaluation=True, human_gold=False,
                             control_type='assistant_screened_author_corrected_same_source',
                             review_note=clean_note)
            accepted.append(candidate)
    assert len(records) == 16 and len(accepted) == 7
    write_rows(OUT/'original16.assistant_review.jsonl', records)
    write_rows(OUT/'clean.accepted7.jsonl', accepted)
    write(OUT/'review_summary.json', {'reviewed': 16, 'clean_candidates': 16, 'accepted': 7, 'held': 9,
          'human_gold': False, 'semantic_accuracy_claimed': False,
          'control_limit': '7 same-source constructed controls, not natural error-free prevalence',
          'finding': 'offsets, content errors and author-label quality all contribute; do not train automatically'})


if __name__ == '__main__':
    main()
