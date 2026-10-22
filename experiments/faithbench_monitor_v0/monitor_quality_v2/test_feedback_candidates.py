from copy import deepcopy
import unittest
from build_feedback_candidates import evidence_cards,examples,restore


class FeedbackCandidateTests(unittest.TestCase):
    def source(self):
        return {'name':'测试店','hours':{'Tuesday':'11:0-20:0','Thursday':'11:0-23:0'},
            'attributes':{'Music':None,'OutdoorSeating':False},
            'review_info':[{'review_text':'这里有现场音乐。','review_stars':5}],
            'nested':{'list':['a',None,{},[]]}}

    def test_all_source_values_survive_shuffled_cards(self):
        source=self.source()
        self.assertEqual(restore(evidence_cards(source,17)),source)
        self.assertEqual(restore(evidence_cards(source,91)),source)
        self.assertNotEqual(evidence_cards(source,17),evidence_cards(source,91))

    def test_time_repair_keeps_day_and_correct_name(self):
        source=self.source();snapshot=deepcopy(source)
        rows=list(examples(source,'g1','ragtruth:1',0))
        bad=next(r for r in rows if r['family']=='time_binding' and r['target']['结论']=='revise')
        self.assertIn('周二营业至23:00',bad['input']['待核回答'])
        self.assertIn('周二关门时间改为20:00',bad['target']['问题'][0]['建议'])
        self.assertIn('测试店',bad['target']['保留'][0]['回答原文'])
        self.assertEqual(source,snapshot)

    def test_null_scope_does_not_erase_supporting_review(self):
        rows=list(examples(self.source(),'g1','ragtruth:1',0))
        bad=next(r for r in rows if r['family']=='null_to_negative' and r['target']['结论']=='revise')
        self.assertIn('仅凭该字段',bad['input']['待核回答'])
        self.assertIn('其他评论仍可能提供支持',bad['target']['问题'][0]['理由'])
        self.assertEqual(restore(bad['input']['证据卡'])['review_info'][0]['review_text'],'这里有现场音乐。')

    def test_citation_pair_keeps_fact_but_changes_source_id(self):
        rows=[r for r in examples(self.source(),'g1','ragtruth:1',0) if r['family']=='citation_binding']
        good,bad=rows
        self.assertEqual(good['pair_id'],bad['pair_id'])
        self.assertNotEqual(good['input']['待核回答'],bad['input']['待核回答'])
        good_id=good['target']['保留'][0]['证据ID']
        self.assertEqual(len(good_id),1)
        self.assertIn('仅把引用',bad['target']['问题'][0]['建议'])

    def test_null_hours_and_all_zero_not_given_closed_semantics(self):
        for hours in (None,{'Monday':'0:0-0:0'}):
            source=self.source();source['hours']=hours
            self.assertFalse(any(r['family'] in ('time_binding','citation_binding') for r in examples(source,'g1','ragtruth:1',0)))


if __name__=='__main__':
    unittest.main()
