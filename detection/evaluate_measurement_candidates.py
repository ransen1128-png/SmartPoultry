"""Evaluate direct endpoint errors and register review-only model suggestions."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison',type=Path,required=True,help='Executed baseline/candidate segmentation comparison JSON')
    parser.add_argument('--dataset',type=Path,default=ROOT/'detection/derived/measurement_v1')
    parser.add_argument('--pose-run',type=Path,default=ROOT/'detection/runs/measurement_pose_v1')
    parser.add_argument('--segment-run',type=Path,default=ROOT/'detection/runs/measurement_segment_v1')
    args=parser.parse_args()
    os.environ['OMP_NUM_THREADS']='2'
    import torch
    torch.set_num_threads(2)
    from ultralytics import YOLO
    from ultralytics.utils.metrics import smooth
    from core.poultry_vision import _box_iou
    from core.spur_measurement import measure_visible_spur
    dataset=args.dataset.resolve()
    manifest=json.loads((dataset/'manifest.json').read_text())
    run=args.pose_run.resolve()
    pose_path=run/'weights/best.pt';pose=YOLO(str(pose_path))
    validation=pose.val(data=str(dataset/'pose/data.yaml'),split='val',imgsz=512,batch=1,device='cpu',workers=0,
                        plots=False,project=str(run),name='direct_endpoint_validation',exist_ok=False,verbose=False)
    chosen=int(smooth(validation.box.f1_curve.mean(0),.1).argmax())
    confidence=float(validation.box.px[chosen])
    comparison=json.loads(args.comparison.read_text())
    baseline_score=comparison['baseline_val']['metrics']['metrics/mAP50(M)']
    candidate_score=comparison['candidate_val']['metrics']['metrics/mAP50(M)']
    old=json.loads((ROOT/'ml_models/poultry_vision/manifest.json').read_text())
    segment_path=(ROOT/'ml_models/poultry_vision'/old['segment']['filename'] if baseline_score>=candidate_score
                  else args.segment_run.resolve()/'weights/best.pt')
    selected='baseline' if baseline_score>=candidate_score else 'candidate'
    threshold=comparison[selected+'_val']['mask_confidence_threshold']
    metrics={};conflicts=[]
    for split in ('val','test'):
        total=0;correct=0;missed_objects=0;errors=[];normalized=[];rows=[]
        for row in (r for r in manifest['rows'] if r['split']==split):
            stem=row['pixel_sha256'][:24];path=dataset/'pose/images'/split/(stem+'.jpg')
            with Image.open(path) as image:width,height=image.size
            truth=[]
            for line in (dataset/'pose/labels'/split/(stem+'.txt')).read_text().splitlines():
                values=list(map(float,line.split()));cx,cy,w,h=values[1:5]
                truth.append({'box':[(cx-w/2)*width,(cy-h/2)*height,(cx+w/2)*width,(cy+h/2)*height],
                              'points':[[values[5]*width,values[6]*height,values[7]],[values[8]*width,values[9]*height,values[10]]]})
            result=pose.predict(str(path),imgsz=512,conf=confidence,iou=.45,max_det=12,device='cpu',verbose=False)[0]
            boxes=result.boxes.xyxy.tolist();pairs=sorted(((_box_iou(t['box'],b),i,j) for i,t in enumerate(truth) for j,b in enumerate(boxes)),reverse=True)
            match={};used=set()
            for overlap,i,j in pairs:
                if overlap>=.5 and i not in match and j not in used:match[i]=j;used.add(j)
            image_errors=[]
            for i,item in enumerate(truth):
                if i not in match:missed_objects+=1
                diagonal=math.hypot(item['box'][2]-item['box'][0],item['box'][3]-item['box'][1])
                for k,point in enumerate(item['points']):
                    if point[2]<=0:continue
                    total+=1
                    if i not in match or float(result.keypoints.conf[match[i],k])<.5:continue
                    error=math.dist(result.keypoints.xy[match[i],k].tolist(),point[:2])
                    errors.append(error);normalized.append(error/max(diagonal,1));image_errors.append(error)
                    correct+=error<=.1*diagonal
            for i,(outline,points) in enumerate(zip(row['annotations']['spurs'],row['endpoint_review']['spurs'])):
                if points['base'] is None or points['tip'] is None:continue
                polygon=[[x*width/600,y*height/600] for x,y in outline]
                base=[points['base'][0]*width/600,points['base'][1]*height/600]
                tip=[points['tip'][0]*width/600,points['tip'][1]*height/600]
                try:measure_visible_spur(polygon,base,tip,width,height,source='assistant_visual_label')
                except ValueError as error:conflicts.append({'index':row['index'],'instance':i,'split':split,'reason':str(error)})
            rows.append({'index':row['index'],'matched_objects':len(match),'ground_truth_objects':len(truth),
                         'endpoint_errors_px':image_errors,'false_positive_boxes':len(boxes)-len(used)})
        metrics[split]={'visible_ground_truth_points':total,'correct_points_at_10pct_spur_box_diagonal':correct,
                        'pck_10pct_including_misses':correct/total if total else None,'matched_point_count':len(errors),
                        'mean_matched_endpoint_error_px':float(np.mean(errors)) if errors else None,
                        'median_matched_endpoint_error_px':float(np.median(errors)) if errors else None,
                        'mean_matched_normalized_error':float(np.mean(normalized)) if normalized else None,
                        'missed_spur_objects':missed_objects,'rows':rows}
    report={'status':'executed_review_only_candidate','promoted':False,'endpoint_box_threshold_from_validation':confidence,
            'endpoint_visibility_threshold':.5,'direct_endpoint_metrics':metrics,'annotation_conflicts':conflicts,
            'outline_model_selected_from_validation':selected,'segmentation_comparison':comparison,
            'limitation':'Visual draft labels and source-family holdouts; independent animal identity and endpoint/physical-length accuracy are not established.'}
    (run/'direct_endpoint_evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    document={'version':1,'purpose':'review_suggestions_only','independent_annotation_verification':False,
              'pose':{'filename':str(pose_path.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(pose_path.read_bytes()).hexdigest(),'threshold':confidence},
              'segment':{'filename':str(segment_path.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(segment_path.read_bytes()).hexdigest(),'threshold':threshold},
              'evaluation':str((run/'direct_endpoint_evaluation.json').relative_to(ROOT)).replace('\\','/')}
    folder=ROOT/'ml_models/spur_measurement';folder.mkdir(exist_ok=True)
    if (folder/'candidates.json').exists():
        previous=(folder/'candidates.json').read_bytes()
        (folder/('candidates_'+hashlib.sha256(previous).hexdigest()[:16]+'.json')).write_bytes(previous)
    temporary=folder/'candidates.json.tmp';temporary.write_text(json.dumps(document,indent=2)+'\n');temporary.replace(folder/'candidates.json')
    print(json.dumps({k:v for k,v in report.items() if k not in ('segmentation_comparison',)},indent=2))


if __name__=='__main__':main()
