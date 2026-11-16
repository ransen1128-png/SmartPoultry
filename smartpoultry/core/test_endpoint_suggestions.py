import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core import endpoint_suggestions as suggestions


class EndpointCandidateGuardTests(TestCase):
    def test_hosted_service_does_not_load_review_candidates(self):
        with patch.dict(os.environ,{'RENDER':'true'}),patch.object(suggestions,'_models',side_effect=AssertionError('Heavy candidate loaded')):
            self.assertIsNone(suggestions.candidate_manifest())
            self.assertEqual(suggestions.suggest_geometry(None,{})['status'],'unavailable')

    def test_wrong_purpose_missing_files_and_escaped_paths_are_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);file=root/'manifest.json'
            for document in ({'purpose':'active'}, {'purpose':'review_suggestions_only','pose':{'filename':'../outside.pt'},'segment':{'filename':'missing.pt'}}):
                file.write_text(json.dumps(document))
                with patch.dict(os.environ,{'RENDER':'','RENDER_EXTERNAL_HOSTNAME':''}),patch.object(suggestions,'ROOT',root),patch.object(suggestions,'MANIFEST',file):
                    self.assertIsNone(suggestions.candidate_manifest())
