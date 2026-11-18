import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from PIL import Image


class MeasurementExportTests(TestCase):
    def setUp(self):
        file=Path(__file__).resolve().parents[2]/'detection/export_measurement_annotations.py'
        spec=importlib.util.spec_from_file_location('measurement_export_under_test',file)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        (self.root/'detection').mkdir();self.rows=[];self.labels={'images':{}}
        outline=[[100,100],[300,100],[300,160],[100,160]]
        for index,(split,color) in enumerate(zip(('train','val','test'),('red','green','blue')),1):
            path=self.root/f'{index}.png';Image.new('RGB',(20,20),color).save(path)
            self.rows.append({'index':index,'image':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                              'pixel_sha256':hashlib.sha256((color+'pixels').encode()).hexdigest(),'source_family':str(index),
                              'split':split,'annotations':{'spurs':[outline]}})
            self.labels['images'][str(index)]={'reviewed_by_human':True,'spurs':[{'base':[100,130],'tip':[300,130],'polygon':outline}]}
        self.save()

    def save(self):
        (self.root/'detection/annotation_manifest.json').write_text(json.dumps(self.rows))
        (self.root/'detection/endpoint_reviews.json').write_text(json.dumps(self.labels))

    def export(self,allow_assistant=False):
        output=self.root/'derived'
        with patch.object(self.module,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()):
            self.module.export(output,allow_assistant)
        return output,json.loads((output/'manifest.json').read_text())

    def test_human_review_gate_and_source_groups_are_enforced(self):
        for item in self.labels['images'].values():item['reviewed_by_human']=False
        self.save()
        with self.assertRaises(ValueError):self.export()
        for item in self.labels['images'].values():item['reviewed_by_human']=True
        self.rows[1]['source_family']=self.rows[0]['source_family'];self.save()
        with self.assertRaises(ValueError):self.export()

    def test_human_outline_and_endpoints_export_without_touching_originals(self):
        before={r['image']:Path(r['image']).read_bytes() for r in self.rows}
        output,report=self.export()
        self.assertEqual(report['complete_endpoint_pairs'],3)
        self.assertEqual(report['label_provenance'],'human_reviewed')
        self.assertFalse(report['independent_annotation_verification'])
        first=next((output/'pose/labels/train').glob('*.txt')).read_text().split()
        self.assertEqual(len(first),11)
        self.assertEqual(float(first[7]),2)
        self.assertEqual(float(first[10]),2)
        for path,content in before.items():self.assertEqual(Path(path).read_bytes(),content)

    def test_unknown_endpoints_use_ignored_visibility_not_invented_locations(self):
        self.labels['images']['1']['spurs'].append({'base':[350,130],'tip':None,'polygon':[[350,100],[450,100],[450,160],[350,160]]})
        self.save();output,report=self.export()
        lines=next((output/'pose/labels/train').glob('*.txt')).read_text().splitlines()
        self.assertEqual([float(v) for v in lines[1].split()[-3:]],[0,0,0])
        self.assertEqual(report['instances'],4)

    def test_inconsistent_reviewed_endpoints_are_rejected_before_training(self):
        self.labels['images']['1']['spurs'][0]['base']=[10,10];self.save()
        with self.assertRaises(ValueError):self.export()
