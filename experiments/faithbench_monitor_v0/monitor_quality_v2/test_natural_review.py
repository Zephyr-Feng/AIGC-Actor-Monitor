import unittest
from prepare_natural_review import excerpt_links,links,original_block
from build_feedback_candidates import evidence_cards,restore


class NaturalReviewTests(unittest.TestCase):
    def test_generated_values_not_used_as_source(self):
        meta='EVIDENT CONFLICT\nOriginal: "WiFi": "no"\nGenerative: "WiFi": "free"'
        self.assertEqual(original_block(meta).strip(),'"WiFi": "no"')
        self.assertEqual(links({'attributes':{'WiFi':'no'}},meta),[(['attributes','WiFi'],'no')])

    def test_null_ambience_and_mismatched_values_not_admitted(self):
        source={'attributes':{'Music':None,'OutdoorSeating':False,'Ambience':{'casual':False}}}
        self.assertEqual(links(source,'Original: "Music": null, "casual": false, "OutdoorSeating": true'),[])
        self.assertEqual(original_block(None),'')

    def test_actual_weekday_and_parking_fields_linked(self):
        source={'hours':{'Thursday':'7:0-21:0'},'attributes':{'BusinessParking':{'lot':False}}}
        self.assertEqual(links(source,'Original: "Thursday": "7:0-21:0", "lot": false'),
            [(['hours','Thursday'],'7:0-21:0'),(['attributes','BusinessParking','lot'],False)])

    def test_exact_unique_source_excerpt_is_not_fuzzy_matched(self):
        source='Two officers chose to resign before the investigation ended.'
        cards=evidence_cards(source,1)
        self.assertEqual(restore(cards),source)
        self.assertEqual(len(excerpt_links(cards,'Original: Two officers chose to resign')),1)
        self.assertEqual(excerpt_links(cards,'Original: Three officers chose to resign'),[])
        self.assertEqual(excerpt_links(evidence_cards(source+' '+source,2),'Original: Two officers chose to resign'),[])


if __name__=='__main__':
    unittest.main()
