import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from inventory_standalone import inventory, references_in, relative_reference
from select_standalone import dependencies
from anonymize_standalone_inputs import transform
from audit_checkpoint_metadata import scan
import zipfile
from unittest.mock import patch
from pack_revision_recipes import normalize
from pack_grid_training import sanitize_metadata


class ReleaseTests(unittest.TestCase):
    def test_tree_audit_checks_archives_strings_and_symlinks_without_unpickling(self):
        path = Path(__file__).resolve().parents[1] / 'clear-standalone/tools/audit_release.py'
        spec = importlib.util.spec_from_file_location('release_audit', path)
        auditor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auditor)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'auditor.py').write_bytes(path.read_bytes())
            (root / 'math.py').write_text('x = matrix.T@np.array([1, 2])\n')
            self.assertEqual(auditor.audit(root, ['private_person'])['status'], 'passed')
            (root / 'metadata.py').write_text('value = "/mnt/archive/model.pt"\n')
            with zipfile.ZipFile(root / 'model.pt', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('weights/data.pkl', b'not a pickle: private_person')
            (root / 'outside').symlink_to(root.parent, target_is_directory=True)
            result = auditor.audit(root, ['private_person'])
            reasons = {r['reason'] for r in result['findings']}
            self.assertIn('supplied identifier', reasons)
            self.assertIn('private path or email requires review', reasons)
            self.assertIn('symlink escapes the package or has no target', reasons)
            self.assertFalse(any('private_person' in str(v) for v in result['findings']))

    def test_recipe_normalization_preserves_command_arguments_and_hashes(self):
        value = {'commands': ['python train.py --data /home/user/project/clear/data/a.json --seed 7'],
                 'checkpoints': {'/home/user/project/clear/model.pt': 'sha256:abc'},
                 'seeds': [7], 'selection_rule': 'validation only'}
        changes = []
        result = normalize(value, changes)
        self.assertEqual(result['commands'], ['python train.py --data ./data/a.json --seed 7'])
        self.assertEqual(result['checkpoints'], {'./model.pt': 'sha256:abc'})
        self.assertEqual(result['seeds'], [7])
        self.assertEqual(result['selection_rule'], value['selection_rule'])
        with self.assertRaises(ValueError):
            normalize({'path': '/home/user/unrecognized/model.pt'}, [])
        with self.assertRaises(ValueError):
            normalize({'/home/one/clear/file': 1, '/home/two/clear/file': 2}, [])

    def test_grid_metadata_scrub_preserves_runtime_parent_and_settings(self):
        value = {'stages': [{'source': 'assets/parent.pt', 'source_sha256': 'frozen',
                  'original_settings': {'source': '/mnt/archive/parent.pt',
                  'root': '/mnt/archive/training', 'steps': 3000, 'lr': 0.0001}}]}
        result = sanitize_metadata(value, [])
        self.assertEqual(result['stages'][0]['source'], 'assets/parent.pt')
        self.assertEqual(result['stages'][0]['source_sha256'], 'frozen')
        self.assertEqual(result['stages'][0]['original_settings']['steps'], 3000)
        self.assertEqual(result['stages'][0]['original_settings']['lr'], 0.0001)
        self.assertTrue(result['stages'][0]['original_settings']['source'].startswith('<ARCHIVE>/'))

    def test_source_identity_uses_exported_bytes_and_detects_local_edits(self):
        template = Path(__file__).parent / 'templates/provenance.py'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / 'runtime/clear'
            package.mkdir(parents=True)
            (root / 'docs').mkdir()
            target = package / 'provenance.py'
            target.write_bytes(template.read_bytes())
            code = package / 'task.py'
            code.write_text('value = 1\n')
            manifest = {'files': {str(p.relative_to(root)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                  for p in (target, code)}}
            (root / 'docs/source_manifest.json').write_text(json.dumps(manifest))
            spec = importlib.util.spec_from_file_location('export_provenance', target)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch('subprocess.check_output', side_effect=AssertionError('Git must not be queried')):
                first = module.package_revision()
                self.assertFalse(first['tracked_changes'])
                code.write_text('value = 2\n')
                second = module.package_revision()
                self.assertTrue(second['tracked_changes'])
                self.assertNotEqual(first['commit'], second['commit'])
                self.assertEqual(second['changed_files'], ['runtime/clear/task.py'])

    def test_anonymization_preserves_labels_and_controller_identity(self):
        source = dict(controller_hash="frozen-controller", probability=0.25,
                      positions=[[1.0, 2.0]], teacher={"recording": "/mnt/private/run"})
        changes = []
        result = transform(source, changes=changes)
        self.assertEqual(changes, ["teacher.recording"])
        self.assertEqual(result["controller_hash"], source["controller_hash"])
        self.assertEqual(result["positions"], source["positions"])
        self.assertEqual(result["probability"], 0.25)
        self.assertEqual(source["teacher"]["recording"], "/mnt/private/run")
        with self.assertRaises(ValueError):
            transform({"controller_checkout": "/mnt/private/runtime"})

    def test_compressed_checkpoint_metadata_is_scanned_without_unpickling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weights.pt"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("weights/data.pkl", b"not a valid pickle; PRIVATE_AUTHOR")
                archive.writestr("weights/data/0", b"tensor bytes")
            self.assertEqual(scan(path, ["private_author"]), ["pickle-metadata"])
            self.assertEqual(scan(path, ["another-identifier"]), [])

    def test_reference_parser_does_not_turn_json_punctuation_into_paths(self):
        self.assertEqual(references_in('"outputs/leap2026/A/result.json",\noutputs/leap2026/**'),
                         {"outputs/leap2026/A/result.json"})
        self.assertIsNone(relative_reference("/external/outputs/../../secrets.pt"))

    def test_store_index_is_not_trusted_without_hashing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            store = Path(tmp) / "store"
            (root / "outputs/leap2026/WP-1").mkdir(parents=True)
            store.mkdir()
            expected = hashlib.sha256(b"original model").hexdigest()
            (root / "outputs/leap2026/PAPER_MAP.md").write_text("outputs/leap2026/WP-1/manifest.json")
            (root / "outputs/leap2026/WP-1/manifest.json").write_text(json.dumps({
                "checkpoints": {"selected": "sha256:" + expected}}))
            (store / "model.pt").write_bytes(b"corrupted model")
            (store / "manifest.json").write_text(json.dumps({"files": {
                "model.pt": {"sha256": expected}}}))
            report = inventory(root, [store])
            self.assertEqual(report["checkpoints"][0]["status"], "missing")
            self.assertEqual(len(report["hash_mismatches"]), 1)
            (store / "model.pt").write_bytes(b"original model")
            report = inventory(root, [store])
            self.assertEqual(report["checkpoints"][0]["status"], "verified")
            self.assertEqual(report["checkpoints"][0]["locations"][0]["origin"], "store-0")
            self.assertEqual((store / "model.pt").read_bytes(), b"original model")

    def test_relative_and_literal_dynamic_imports_are_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "clear"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "local.py").write_text("x = 1")
            (pkg / "dynamic.py").write_text("")
            (pkg / "entry.py").write_text('from .local import x\nPLUGIN="clear.dynamic"\n')
            imports, _ = dependencies(root, "clear.entry")
            self.assertIn("clear.local", imports)
            self.assertIn("clear.dynamic", imports)

    def test_launcher_rejects_unsupported_combination(self):
        path = Path(__file__).resolve().parents[1] / "clear-standalone/run.py"
        spec = importlib.util.spec_from_file_location("standalone_launcher", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(SystemExit) as error:
            module.main(["plan", "grid"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
