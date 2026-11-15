"""Fail the build on missing/incompatible compiled inference dependencies."""
import importlib.metadata


def check_runtime():
    import cv2
    import torch
    from torchvision.ops import nms
    from transformers import OwlViTProcessor,OwlViTForObjectDetection
    from ultralytics import YOLO
    from skimage.morphology import skeletonize
    expected={'transformers':'4.57.6','tokenizers':'0.22.2','safetensors':'0.8.0','ultralytics':'8.3.221'}
    for package,version in expected.items():
        installed=importlib.metadata.version(package)
        if installed!=version:raise RuntimeError(f'{package} must match the desktop version {version}; found {installed}')
    if cv2.__version__!='4.11.0':raise RuntimeError('OpenCV version differs from the desktop inference build')
    selected=nms(torch.tensor([[0.,0.,10.,10.]]),torch.tensor([.8]),.5)
    if selected.tolist()!=[0]:raise RuntimeError('Compiled CPU nonmaximum suppression check failed')
    print('Full inference dependency imports, desktop version pins and CPU NMS verified.',flush=True)


if __name__=='__main__':check_runtime()
