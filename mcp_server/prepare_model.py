"""Prepare the pinned local model; never downloads an entire snapshot."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from mcp_server.rag import MODEL, REVISION

FILES = ('config.json', 'config_sentence_transformers.json', 'modules.json',
         'model.safetensors', 'sentence_bert_config.json', 'special_tokens_map.json',
         'tokenizer.json', 'tokenizer_config.json', '1_Pooling/config.json')
DEST = Path(__file__).resolve().parents[1] / '.rag-index/models-verified'


def main():
    roots = [DEST.parent / 'models', Path.home() / '.cache/huggingface/hub']
    hashes = {}
    for name in FILES:
        target = DEST / name
        if not target.is_file() or target.stat().st_size == 0:
            for root in roots:
                source = root / ('models--' + MODEL.replace('/', '--')) / 'snapshots' / REVISION / name
                if source.is_file() and source.stat().st_size:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    break
            else:
                subprocess.run([sys.executable, '-c',
                    'import sys; from huggingface_hub import hf_hub_download; '
                    'hf_hub_download(sys.argv[1], sys.argv[2], revision=sys.argv[3], '
                    'local_dir=sys.argv[4], etag_timeout=10)',
                    MODEL, name, REVISION, str(DEST)], timeout=60, check=True)
        if not target.stat().st_size:
            raise ValueError(f'Empty model file: {name}')
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        if name.endswith('.json'):
            json.loads(target.read_text(encoding='utf-8'))
    from safetensors import safe_open
    with safe_open(DEST / 'model.safetensors', framework='pt') as tensors:
        assert len(tensors.keys()) > 0
    (DEST / 'verified.json').write_text(json.dumps(
        dict(model=MODEL, revision=REVISION, hashes=hashes), indent=2), encoding='utf-8')
    print(f'Verified {len(hashes)} local model files', flush=True)


if __name__ == '__main__':
    main()
