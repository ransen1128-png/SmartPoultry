"""Build an offline visual editor for the existing dataset's draft annotations."""
import base64
import argparse
import copy
import json
import hashlib
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
from core.spur_measurement import contains_point


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',type=Path,default=ROOT/'detection/endpoint_reviews.json')
    args=parser.parse_args()
    seed=json.loads(args.labels.read_text())
    document=copy.deepcopy(seed);items=[]
    existing=json.loads((ROOT/'detection/annotation_manifest.json').read_text())
    partial=json.loads((ROOT/'detection/manual_annotations.json').read_text())['images']
    lookup={r['index']:r for r in existing};family_splits={r['source_family']:r['split'] for r in existing}
    sources=[]
    for source in json.loads((ROOT/'detection/annotation_views/index.json').read_text()):
        row=lookup.get(source['index'])
        if row is None:
            family=source['source_family']
            fold=int(hashlib.sha256(('measurement-v1:'+family).encode()).hexdigest()[:8],16)%10
            split=family_splits.setdefault(family,'train' if fold<6 else 'val' if fold<8 else 'test')
            row={**source,'split':split,'annotations':partial.get(str(source['index']),{'spurs':[]}),
                 'existing_annotation':False}
        sources.append(row)
        key=str(row['index'])
        entry=document['images'].setdefault(key,{'spurs':[{'base':None,'tip':None} for _ in row['annotations']['spurs']]})
        for instance,polygon in zip(entry['spurs'],row['annotations']['spurs']):instance.setdefault('polygon',polygon)
        entry.setdefault('reviewed_by_human',False)
        with Image.open(row['image']) as original:
            preview=ImageOps.exif_transpose(original).convert('RGB').resize((600,600))
            stream=BytesIO();preview.save(stream,format='JPEG',quality=90)
        issues=[]
        for instance_index,instance in enumerate(entry['spurs']):
            for name in ('base','tip'):
                if instance[name] is not None and not contains_point(instance[name],instance['polygon']):
                    issues.append(f'Spur {instance_index+1}: {name} outside draft outline')
        items.append({'index':row['index'],'split':row['split'],'family':row['source_family'],'issues':issues,
                      'image':'data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode()})
    template=(ROOT/'detection/endpoint_review_template.html').read_text()
    data=json.dumps({'document':document,'items':items}).replace('<',r'\u003c').replace('>',r'\u003e').replace('&',r'\u0026')
    output=ROOT/'detection/annotation_review/measurement_editor.html';output.parent.mkdir(exist_ok=True)
    output.write_text(template.replace('__REVIEW_DATA__',data),encoding='utf-8')
    (ROOT/'detection/measurement_source_manifest.json').write_text(json.dumps(sources,indent=2)+'\n')
    print('Offline review editor:',output)
    print('Existing distinct photographs available for review:',len(items))


if __name__=='__main__':main()
