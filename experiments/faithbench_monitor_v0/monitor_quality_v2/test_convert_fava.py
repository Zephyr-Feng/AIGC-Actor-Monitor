import tempfile
import unittest
from pathlib import Path
from convert_fava import convert, run


def row(answer, annotated):
    return {'prompt': 'Read the following references:\nReference [1]: A is correct.\n'
            'Please identify all the errors in the following passage using the references provided and suggest edits:\nText: ' + answer,
            'completion': annotated}


class ConversionTests(unittest.TestCase):
    def test_replacement_direction_and_exact_repeated_position(self):
        r = convert(row('B & B', 'B & <entity><mark>A</mark><delete>B</delete></entity>'), 1)
        i = r['supervision']['issues'][0]
        self.assertEqual((i['start'], i['end'], i['quote'], i['replacement']), (4, 5, 'B', 'A'))
        self.assertEqual(r['supervision']['corrected_answer'], 'B & A')
        self.assertIsNone(i['evidence_ids'])
        self.assertFalse(r['approved_for_training'])

    def test_deletion_and_insertion(self):
        r = convert(row('Bad. ', '<contradictory><delete>Bad.</delete></contradictory> '
                        '<entity><mark>A</mark></entity>'), 1)
        self.assertEqual(r['supervision']['corrected_answer'], ' A')
        self.assertEqual(r['supervision']['issues'][1]['quote'], '')

    def test_unresolved_annotation_does_not_become_corrected_answer(self):
        r = convert(row('Bad.', '<unverifiable>Bad.</unverifiable>'), 1)
        self.assertIsNone(r['supervision']['corrected_answer'])
        self.assertIsNone(r['supervision']['issues'][0]['replacement'])
        self.assertIsNone(r['supervision']['protected_content'])

    def test_malformed_unknown_and_mismatched_text_rejected(self):
        for annotation in ['<entity>Bad.', '<typo>Bad.</typo>', '<entity>Different.</entity>']:
            with self.subTest(annotation=annotation), self.assertRaises(ValueError):
                convert(row('Bad.', annotation), 1)

    def test_quarantine_count_and_no_overwrite(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'raw.json'
            source.write_text(json.dumps([row('B', '<entity><mark>A</mark><delete>B</delete></entity>'),
                                          row('B', '<entity>B')]), encoding='utf8')
            result = run(source, base / 'out')
            self.assertEqual((result['converted'], result['quarantined']), (1, 1))
            with self.assertRaises(FileExistsError):
                run(source, base / 'out')


if __name__ == '__main__':
    unittest.main()
