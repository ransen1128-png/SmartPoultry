"""Export existing trained weights for a smaller CPU inference runtime.

Exports are separate artifacts. No training or original checkpoint changes.
"""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
OUT=ROOT/'ml_models/free_runtime'
WORK=ROOT/'.cache-huggingface/free-export'


def write_manifest():
    from core.free_inference import CHICKEN_STAGES
    entries=[]
    for name in ('age.onnx','age.json',*CHICKEN_STAGES,'chicken.json','detect.onnx','segment.onnx'):
        path=OUT/name;checksum=hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda:source.read(1024*1024),b''):checksum.update(block)
        entries.append({'filename':name,'bytes':path.stat().st_size,'sha256':checksum.hexdigest()})
    (OUT/'manifest.json').write_text(json.dumps({'version':2,'runtime':'onnxruntime-1.23.2','age_precision':'float32','anatomy_precision':'float32','chicken_precision':'float32-staged','files':entries},indent=2)+'\n')


def export_chicken_stages():
    import onnx
    from core.free_inference import CHICKEN_STAGES
    source=WORK/'chicken.fp32.onnx'
    boundaries=['pixels']+[f'/vision_model/encoder/layers.{n}/Add_1_output_0' for n in (2,5,8,11)]
    for index,start in enumerate(boundaries):
        end=[boundaries[index+1]] if index+1<len(boundaries) else ['logits','boxes']
        target=OUT/CHICKEN_STAGES[index]
        onnx.utils.extract_model(str(source),str(target),[start],end,check_model=True)
        print(target.name,target.stat().st_size,flush=True)
    meta=json.loads((OUT/'chicken.json').read_text())
    meta.pop('quantization',None);meta.update(precision='float32',stages=list(CHICKEN_STAGES))
    (OUT/'chicken.json').write_text(json.dumps(meta,indent=2))


def export(task):
    if task=='manifest':write_manifest();return
    if task=='chicken-stages':export_chicken_stages();return
    import torch
    torch.set_num_threads(1)
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    if task=='age':
        from core.rooster_age_classifier import _load_ready_model
        artifact=_load_ready_model('finetuned')
        if artifact is None:raise RuntimeError('Verified age checkpoint unavailable')
        size=artifact['transform'].transforms[0].size[0]
        target=OUT/'age.onnx'
        torch.onnx.export(artifact['model'],torch.zeros(1,3,size,size),str(target),input_names=['pixels'],output_names=['age'],opset_version=17,dynamo=False)
        meta={k:artifact[k] for k in ('age_min','age_max','test_mae','sha256','model_variant','comparison_metrics','evaluation_status')}
        meta.update(image_size=size,mean=artifact['transform'].transforms[2].mean,std=artifact['transform'].transforms[2].std)
        (OUT/'age.json').write_text(json.dumps(meta,indent=2))
    elif task in ('detect','segment'):
        from ultralytics import YOLO
        manifest=json.loads((ROOT/'ml_models/poultry_vision/manifest.json').read_text())
        original=ROOT/'ml_models/poultry_vision'/manifest[task]['filename']
        clone=WORK/(task+'.pt');shutil.copyfile(original,clone)
        model=YOLO(str(clone))
        result=model.export(format='onnx',imgsz=512,batch=1,dynamic=True,simplify=False,opset=17,device='cpu')
        target=OUT/(task+'.onnx');shutil.copyfile(result,target)
    else:
        from core.chicken_detection import load_detector,BODY_QUERIES
        processor,model=load_detector()
        inputs=processor(text=[BODY_QUERIES],return_tensors='pt')
        with torch.inference_mode():
            query=model.owlvit.get_text_features(**inputs).reshape(1,4,-1)
        class ImageDetector(torch.nn.Module):
            def __init__(self):
                super().__init__();self.model=model;self.register_buffer('query',query);self.register_buffer('query_mask',(inputs['input_ids'][:,0]>0).reshape(1,4))
            def forward(self,pixels):
                feature_map,_=self.model.image_embedder(pixels)
                features=feature_map.reshape(1,-1,feature_map.shape[-1])
                logits,_=self.model.class_predictor(features,self.query,self.query_mask)
                boxes=self.model.box_predictor(features,feature_map)
                return logits,boxes
        wrapper=ImageDetector().eval()
        target=WORK/'chicken.fp32.onnx'
        torch.onnx.export(wrapper,torch.zeros(1,3,768,768),str(target),input_names=['pixels'],output_names=['logits','boxes'],opset_version=17,dynamo=False)
        (OUT/'chicken.json').write_text(json.dumps({'queries':BODY_QUERIES,'image_processor':processor.image_processor.to_dict(),'source_sha256':'40b0fbb7b18a468417dd1786d035d993a8414706bb4b16098cfc1edbdba6031e'},indent=2))
        export_chicken_stages()
    print(task,'exported',target.stat().st_size,'bytes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('task',choices=['age','detect','segment','chicken','chicken-stages','manifest'])
    export(parser.parse_args().task)
