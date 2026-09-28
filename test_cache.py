from transformers import AutoTokenizer
import os

model_id = 'Qwen/Qwen2.5-7B-Instruct'
print('Testing cache for', model_id)
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=True)
print('Tokenizer loaded successfully from cache.')
print('Vocab size:', tok.vocab_size)
print('Cache test passed.')