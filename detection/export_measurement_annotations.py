"""Export real visual outline/endpoint annotations without changing originals."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def export(output, allow_assistant=False, review_path=None):
    review_path = review_path or ROOT/'detection/endpoint_reviews.json'
    review = json.loads(review_path.read_text())
    source_manifest=ROOT/'detection/measurement_source_manifest.json'
    if not source_manifest.exists():source_manifest=ROOT/'detection/annotation_manifest.json'
    rows = json.loads(source_manifest.read_text())
    selected, excluded, family_splits, pixel_splits, conflicts = [], [], {}, {}, []
    for row in rows:
        entry = review['images'].get(str(row['index']))
        if entry is None:
            excluded.append({'index':row['index'], 'reason':'Endpoint review pending; not a negative image.'})
            continue
        if entry.get('exclude_from_training') or (not allow_assistant and not entry.get('reviewed_by_human')):
            excluded.append({'index':row['index'],'reason':'Excluded or human review pending; not a negative image.'})
            continue
        originals = row['annotations']['spurs']
        if all('polygon' in p for p in entry['spurs']):
            outlines=[p['polygon'] for p in entry['spurs']]
        elif len(entry['spurs'])==len(originals):outlines=originals
        else:
            raise ValueError(f'Instance mismatch: image {row["index"]}')
        negative=(not outlines and entry.get('reviewed_by_human') is True and entry.get('negative_visible_spur_verified') is True)
        if not negative and not any(item['base'] is not None and item['tip'] is not None for item in entry['spurs']):
            excluded.append({'index':row['index'], 'reason':entry.get('note','No fully visible endpoint pair.')})
            continue
        source = Path(row['image'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f'Original changed: {row["index"]}')
        for token, mapping in ((row['source_family'], family_splits), (row['pixel_sha256'], pixel_splits)):
            if token in mapping and mapping[token] != row['split']:
                raise ValueError('Source-family or identical-pixel leakage')
            mapping[token] = row['split']
        for instance in entry['spurs']:
            for name in ('base','tip'):
                point = instance[name]
                if point is not None and (len(point)!=2 or any(type(v) not in (int,float) or not 0<=v<=600 for v in point)):
                    raise ValueError('Invalid visible keypoint')
        sys_path=str(ROOT/'smartpoultry')
        import sys
        if sys_path not in sys.path:sys.path.insert(0,sys_path)
        from core.spur_measurement import validate_outline, contains_point
        for instance_index,(outline,endpoints) in enumerate(zip(outlines,entry['spurs'])):
            validated=validate_outline(outline,601,601)
            for name in ('base','tip'):
                if endpoints[name] is not None and not contains_point(endpoints[name],validated):
                    issue={'index':row['index'],'instance':instance_index,'endpoint':name,'reason':'Endpoint outside visible outline.'}
                    conflicts.append(issue)
                    if not allow_assistant:raise ValueError(f'Image {row["index"]}, spur {instance_index+1}: correct the {name} or outline before training.')
        selected.append({**row, 'annotations':{**row['annotations'],'spurs':outlines},'endpoint_review':entry})
    if set(row['split'] for row in selected) != {'train','val','test'}:
        raise ValueError('A separated train/validation/test dataset is required')
    for split in ('train','val','test'):
        if not any(r['split']==split and any(p['base'] is not None and p['tip'] is not None for p in r['endpoint_review']['spurs']) for r in selected):
            raise ValueError(f'{split} needs at least one visible endpoint pair; negatives alone cannot supervise endpoints.')
    output.mkdir(parents=True, exist_ok=False)
    for row in selected:
        with Image.open(row['image']) as raw:
            image = ImageOps.exif_transpose(raw).convert('RGB')
        stem = row['pixel_sha256'][:24]
        pose_lines, segment_lines = [], []
        for outline, points in zip(row['annotations']['spurs'], row['endpoint_review']['spurs']):
            known = outline + [points[key] for key in ('base','tip') if points[key] is not None]
            x1, y1 = min(p[0] for p in known), min(p[1] for p in known)
            x2, y2 = max(p[0] for p in known), max(p[1] for p in known)
            values = [(x1+x2)/1200, (y1+y2)/1200, (x2-x1)/600, (y2-y1)/600]
            for key in ('base','tip'):
                point = points[key]
                values.extend([point[0]/600, point[1]/600, 2] if point is not None else [0,0,0])
            pose_lines.append('0 '+' '.join(f'{v:.8f}' for v in values))
            segment_lines.append('0 '+' '.join(f'{v/600:.8f}' for point in outline for v in point))
        for task, lines in (('pose',pose_lines),('segment',segment_lines)):
            folder = output/task
            images, labels = folder/'images'/row['split'], folder/'labels'/row['split']
            images.mkdir(parents=True, exist_ok=True);labels.mkdir(parents=True, exist_ok=True)
            image.save(images/(stem+'.jpg'), quality=96)
            (labels/(stem+'.txt')).write_text('\n'.join(lines)+'\n')
    for task in ('pose','segment'):
        folder = output/task
        extra = 'kpt_shape: [2, 3]\nflip_idx: [0, 1]\n' if task=='pose' else ''
        (folder/'data.yaml').write_text(f'path: {folder.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\n{extra}names:\n  0: spur\n')
    report = {'status':'experimental_assistant_visual_labels' if allow_assistant else 'human_reviewed_training_labels', 'original_annotated_images':len(rows),
              'images':len(selected), 'instances':sum(len(r['endpoint_review']['spurs']) for r in selected),
              'complete_endpoint_pairs':sum(p['base'] is not None and p['tip'] is not None for r in selected for p in r['endpoint_review']['spurs']),
              'splits':dict(Counter(r['split'] for r in selected)), 'source_family_leakage':False,
              'independent_chicken_ids_verified':False, 'independent_annotation_verification':False,
              'label_provenance':'assistant_visual_review' if allow_assistant else 'human_reviewed',
              'annotation_sha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),
              'annotation_conflicts':conflicts,
              'excluded':excluded, 'rows':selected}
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'detection/derived/measurement_v1')
    parser.add_argument('--allow-assistant-labels',action='store_true')
    parser.add_argument('--labels',type=Path,default=ROOT/'detection/endpoint_reviews.json')
    args=parser.parse_args();export(args.output.resolve(),args.allow_assistant_labels,args.labels.resolve())
