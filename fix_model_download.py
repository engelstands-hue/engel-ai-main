from huggingface_hub import snapshot_download
import os

model_id = 'Qwen/Qwen2.5-7B-Instruct'
cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
print('Ensuring full cache for', model_id)
path = snapshot_download(
    repo_id=model_id,
    cache_dir=cache_dir,
    resume_download=True,
    local_files_only=False,
    force_download=False
)
print('Model cached at:', path)
files = [f for f in os.listdir(path) if f.endswith('.safetensors') or 'model' in f]
print('Relevant files:', len(files))
print('Done.')