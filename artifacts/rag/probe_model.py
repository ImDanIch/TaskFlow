"""Bounded offline initialization diagnostic, without MCP or downloads."""
import faulthandler
import os
import time

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
faulthandler.dump_traceback_later(25, repeat=False)
started = time.monotonic()
print('stage: import sentence_transformers', flush=True)
from sentence_transformers import SentenceTransformer
print(f'stage: import complete {time.monotonic()-started:.2f}s; load local model', flush=True)
from mcp_server.rag import SentenceEncoder
encoder = SentenceEncoder(None)
print('dimensions:', len(encoder.encode(['збереження завдань'])[0]), flush=True)
faulthandler.cancel_dump_traceback_later()
print(f'complete {time.monotonic()-started:.2f}s', flush=True)
