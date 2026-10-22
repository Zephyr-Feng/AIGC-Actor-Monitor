import json
from pathlib import Path
import struct
import tempfile
import unittest

from fix_proposed_overlap import canonical
from train_feedback import adapter_structure


class TrainingGuardTests(unittest.TestCase):
    def test_content_identity_ignores_remapped_evidence_ids(self):
        a={'messages':[{'role':'system','content':'s'},{'role':'user','content':json.dumps({'证据卡':[{'id':'E1','path':['a'],'value':7}],'待核回答':'数字是7【E1】'})}]}
        b={'messages':[{'role':'system','content':'s'},{'role':'user','content':json.dumps({'证据卡':[{'id':'E99','path':['a'],'value':7}],'待核回答':'数字是7【E99】'})}]}
        self.assertEqual(canonical(a),canonical(b))

    def test_truncated_adapter_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'adapter').mkdir()
            header=json.dumps({'weight':{'dtype':'F32','shape':[1],'data_offsets':[0,4]}}).encode()
            file=root/'adapter/adapter_model.safetensors'
            file.write_bytes(struct.pack('<Q',len(header))+header+b'1234')
            (root/'adapter/adapter_config.json').write_text('{"r":8}')
            (root/'training_state.pt').write_bytes(b'state')
            self.assertTrue(adapter_structure(root)['payload_structure_valid'])
            file.write_bytes(file.read_bytes()[:-1])
            with self.assertRaises(AssertionError):adapter_structure(root)


if __name__=='__main__':
    unittest.main()
