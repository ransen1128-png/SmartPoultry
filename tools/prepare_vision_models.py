"""Install and verify the desktop's exact vision checkpoints during the build.

No downloads take place during HTTP requests. Original local files are never
replaced. The public OWL-ViT source is revision- and checksum-pinned; removing
two nonpersistent position-id buffers reproduces the desktop safetensors file.
"""
import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'ml_models/deployment.json'


def digest(path):
    checksum=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            checksum.update(block)
    return checksum.hexdigest()


def local_path(root,relative):
    path=(root/relative).resolve()
    path.relative_to(root.resolve())
    return path


def verify(path,entry):
    if not path.is_file():raise ValueError(f'Missing vision asset: {entry["path"]}')
    if path.stat().st_size!=entry['bytes'] or digest(path)!=entry['sha256']:
        raise ValueError(f'Vision asset does not match the verified desktop file: {entry["path"]}')


def prepare(root=ROOT,verify_only=False):
    manifest=json.loads((root/'ml_models/deployment.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        verify(local_path(root,entry['path']),entry)
    entry=manifest['chicken_checkpoint'];target=local_path(root,entry['path'])
    if target.exists():
        verify(target,entry)
    elif verify_only:
        raise ValueError('Chicken detector is missing. Run the model build preparation first.')
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        # The temporary directory is owned by this operation and stays inside
        # the intended model folder; cleanup cannot affect original assets.
        with tempfile.TemporaryDirectory(prefix='build-',dir=target.parent) as folder:
            folder=Path(folder).resolve();folder.relative_to(target.parent.resolve())
            downloaded=folder/'upstream.safetensors'
            print('Downloading pinned public chicken checkpoint for this build...',flush=True)
            with urllib.request.urlopen(entry['source']['url'],timeout=120) as response,downloaded.open('wb') as output:
                for block in iter(lambda:response.read(8*1024*1024),b''):output.write(block)
            if digest(downloaded)!=entry['source']['sha256']:
                raise ValueError('Downloaded chicken checkpoint failed its source integrity check.')
            from safetensors import safe_open
            from safetensors.torch import save_file
            with safe_open(str(downloaded),framework='pt',device='cpu') as source:
                tensors={name:source.get_tensor(name) for name in source.keys() if name not in entry['source']['omit_nonpersistent_buffers']}
                converted=folder/'model.safetensors'
                save_file(tensors,str(converted),metadata={'format':'pt'})
                verify(converted,entry)
            del tensors
            del source
            if target.exists():raise ValueError('Target appeared during preparation; refusing to replace it.')
            converted.replace(target)
    print(f'Verified {len(manifest["files"])+1} vision assets against the desktop hashes.',flush=True)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only',action='store_true')
    arguments=parser.parse_args()
    prepare(verify_only=arguments.verify_only)
