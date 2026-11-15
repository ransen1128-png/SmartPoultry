import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from prepare_vision_models import prepare


class VisionAssetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'ml_models').mkdir()
        self.config=self.root/'ml_models/config.json';self.config.write_bytes(b'{}')
        self.model=self.root/'ml_models/model.safetensors';self.model.write_bytes(b'verified-model')
        def entry(path):
            data=path.read_bytes()
            return {'path':path.relative_to(self.root).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        self.manifest={'files':[entry(self.config)],'chicken_checkpoint':entry(self.model)}
        self.write_manifest()

    def write_manifest(self):
        (self.root/'ml_models/deployment.json').write_text(json.dumps(self.manifest))

    def test_existing_exact_assets_are_reused_without_network_or_modification(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected download')):
            prepare(self.root,verify_only=True)
            prepare(self.root)
        self.assertEqual(self.model.read_bytes(),b'verified-model')

    def test_corrupt_local_checkpoint_is_reported_and_never_replaced(self):
        self.model.write_bytes(b'changed')
        with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected download')):
            with self.assertRaisesRegex(ValueError,'does not match'):prepare(self.root)
        self.assertEqual(self.model.read_bytes(),b'changed')

    def test_missing_checkpoint_fails_verify_only(self):
        self.model.unlink()
        with self.assertRaisesRegex(ValueError,'missing'):prepare(self.root,verify_only=True)

    def test_asset_paths_cannot_escape_bundle_root(self):
        self.manifest['files'][0]['path']='../outside.json';self.write_manifest()
        with self.assertRaises(ValueError):prepare(self.root,verify_only=True)
