import pickle
from pathlib import Path
import tempfile
import unittest
import zipfile

from anonymize_standalone_checkpoints import (
    collect_replacements, compare_values, derive, rewrite_pickle, sha)


class CheckpointDerivatives(unittest.TestCase):
    def test_only_approved_fields_can_change(self):
        value = {'development_study': {'root': '/mnt/private/run'}, 'model': {'layer': 'unchanged'}}
        mapping, fields = collect_replacements(value, ['private'])
        self.assertEqual(fields, ['development_study.root'])
        restored = pickle.loads(rewrite_pickle(pickle.dumps(value, protocol=2), mapping))
        self.assertEqual(restored['model'], value['model'])
        self.assertTrue(restored['development_study']['root'].startswith('<ARCHIVE>/'))
        with self.assertRaises(ValueError):
            collect_replacements({'unexpected': '/mnt/private/run'}, ['private'])
        with self.assertRaises(ValueError):
            collect_replacements({'/mnt/private/key': 1}, ['private'])
        with self.assertRaises(ValueError):
            rewrite_pickle(pickle.dumps(value, protocol=4), mapping)
        with self.assertRaises(ValueError):
            rewrite_pickle(pickle.dumps(value, protocol=2) + b'extra', mapping)

    def test_memoized_string_cannot_change_an_unapproved_field(self):
        import torch
        value = '/mnt/private/run'
        before = {'development_study': {'root': value}, 'other': value, 'model': torch.ones(1)}
        after = {'development_study': {'root': '<ARCHIVE>/x'}, 'other': '<ARCHIVE>/x', 'model': torch.ones(1)}
        with self.assertRaises(ValueError):
            compare_values(before, after, {value: '<ARCHIVE>/x'})

    def test_zip_tensor_bytes_optimizer_state_and_original_are_preserved(self):
        import torch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target, second = (root / s for s in ['original.pt', 'anonymous.pt', 'second.pt'])
            weight = torch.arange(12, dtype=torch.float64).reshape(3, 4)
            torch.save({'model': {'weight': weight, 'view': weight[:, 1:]},
                        'optimizer': {'momentum': torch.ones(3, 4), 'step': 25},
                        'development_study': {'root': '/mnt/private/run'}, 'seed': 42}, source)
            original_hash = sha(source)
            first = derive(source, target, original_hash, ['private'])
            derive(source, second, original_hash, ['private'])
            self.assertEqual(sha(source), original_hash)
            self.assertEqual(sha(target), sha(second))
            self.assertNotEqual(sha(target), original_hash)
            self.assertEqual(first['tensor_count'], 3)
            with zipfile.ZipFile(source) as src, zipfile.ZipFile(target) as dst:
                self.assertEqual(src.namelist(), dst.namelist())
                for name in src.namelist():
                    if not name.endswith('/data.pkl'):
                        self.assertEqual(src.read(name), dst.read(name))
            result = torch.load(target, weights_only=False)
            self.assertEqual(result['model']['weight'].untyped_storage().data_ptr(),
                             result['model']['view'].untyped_storage().data_ptr())
            with self.assertRaises(ValueError):
                derive(source, source, original_hash, ['private'])
            with self.assertRaises(ValueError):
                derive(source, target, 'wrong hash', ['private'])


if __name__ == '__main__':
    unittest.main()
