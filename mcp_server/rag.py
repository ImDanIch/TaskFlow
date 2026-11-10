"""Local, policy-filtered Markdown embeddings; no KB writes or remote inference."""

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import logging

LOG = logging.getLogger(__name__)
_MODEL_LOCK = threading.Lock()
_MODELS = {}


MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
VERSION = 1
CHUNK_SIZE = 600
OVERLAP = 100
MODEL_FILES = {'config.json', 'config_sentence_transformers.json', 'modules.json',
               'model.safetensors', 'sentence_bert_config.json', 'special_tokens_map.json',
               'tokenizer.json', 'tokenizer_config.json', '1_Pooling/config.json'}


def chunk_text(text, size=CHUNK_SIZE, overlap=OVERLAP):
    """Deterministic character windows; retain exact source offsets and overlap."""
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    for start in range(0, len(text), size - overlap):
        end = min(start + size, len(text))
        if text[start:end].strip():
            yield start, end, text[start:end]
        if end == len(text):
            break


class SentenceEncoder:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.model = None
        self.lock = _MODEL_LOCK

    def encode(self, texts):
        with self.lock:
            if self.model is None:
                started = time.monotonic()
                local = Path(__file__).resolve().parents[1] / '.rag-index/models-verified'
                key = str(local)
                if key in _MODELS:
                    self.model = _MODELS[key]
                else:
                    try:
                        manifest = json.loads((local / 'verified.json').read_text(encoding='utf-8'))
                        if manifest['model'] != MODEL or manifest['revision'] != REVISION:
                            raise ValueError('Model revision mismatch')
                        if set(manifest['hashes']) != MODEL_FILES:
                            raise ValueError('Model manifest must cover every required file')
                        for name, digest in manifest['hashes'].items():
                            if hashlib.sha256((local / name).read_bytes()).hexdigest() != digest:
                                raise ValueError(f'Model checksum mismatch: {name}')
                    except (OSError, KeyError, ValueError) as exc:
                        raise RuntimeError('Local model incomplete; run python -m mcp_server.prepare_model') from exc
                    LOG.info("Loading verified local embedding model")
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer(str(local), local_files_only=True,
                                                     device='cpu', trust_remote_code=False)
                    self.model.max_seq_length = 256
                    _MODELS[key] = self.model
                LOG.info('Embedding model ready in %.2fs', time.monotonic() - started)
            return self.model.encode(texts, normalize_embeddings=True,
                                     show_progress_bar=False).tolist()


def normalized(vector):
    vector = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in vector))
    if not vector or not math.isfinite(norm) or norm == 0:
        raise ValueError("Invalid embedding")
    return [value / norm for value in vector]


class VectorIndex:
    def __init__(self, vault, index_dir=None, encoder=None):
        self.vault = vault
        self.directory = Path(index_dir or Path(__file__).resolve().parents[1] / ".rag-index")
        if self.directory.resolve().is_relative_to(vault.root):
            raise ValueError("Vector index must be outside the knowledge-base vault")
        key = hashlib.sha256(str(vault.root).encode()).hexdigest()[:24]
        self.path = self.directory / f"{key}.json"
        self.encoder = encoder or SentenceEncoder(self.directory / "models")
        self.lock = threading.Lock()
        self._cached = None
        self._stamp = None

    def _snapshot(self):
        notes = dict(self.vault.iter_notes())
        chunks = []
        for path, text in notes.items():
            for start, end, content in chunk_text(text):
                chunks.append(dict(path=path, start=start, end=end, text=content))
        fingerprint = hashlib.sha256(json.dumps(
            [str(self.vault.root), MODEL, REVISION, VERSION, CHUNK_SIZE, OVERLAP, notes,
             self.vault.policy.policy], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return fingerprint, chunks

    def _load(self, fingerprint, chunks):
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
            if cached["fingerprint"] != fingerprint or cached["chunks"] != chunks:
                return None
            vectors = [normalized(row) for row in cached["vectors"]]
            if len(vectors) != len(chunks) or len({len(row) for row in vectors}) > 1:
                return None
            return vectors
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            return None

    def _save(self, fingerprint, chunks, vectors):
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = dict(fingerprint=fingerprint, model=MODEL, revision=REVISION,
                       chunks=chunks, vectors=vectors)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                             suffix=".tmp", delete=False) as stream:
                temporary = stream.name
                json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def build_index(self, timeout=300):
        """Build once explicitly; searches never scan or re-embed the vault."""
        started = time.monotonic()
        with self.lock:
            fingerprint, chunks = self._snapshot()
            cached = self._load(fingerprint, chunks)
            if cached is not None:
                return len(chunks)
            if time.monotonic() - started > timeout:
                raise TimeoutError("RAG index preparation timed out")
            LOG.info("Building RAG index: %d chunks", len(chunks))
            vectors = [normalized(row) for row in self.encoder.encode(
                [f"{chunk['path']}\n{chunk['text']}" for chunk in chunks])] if chunks else []
            if len(vectors) != len(chunks) or len({len(row) for row in vectors}) > 1:
                raise ValueError("Inconsistent embedding dimensions")
            if time.monotonic() - started > timeout:
                raise TimeoutError("RAG index embedding timed out")
            self._save(fingerprint, chunks, vectors)
            LOG.info("RAG index ready: %d chunks", len(chunks))
            return len(chunks)

    def search(self, query, limit=5):
        """Return best chunk per note, ranked by cosine; score is not confidence."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query must not be blank")
        with self.lock:
            stamp = (self.path.stat().st_mtime_ns, self.path.stat().st_size)
            if self._cached is None or stamp != self._stamp:
                cached = json.loads(self.path.read_text(encoding="utf-8"))
                if cached['model'] != MODEL or cached['revision'] != REVISION:
                    raise ValueError('Incompatible index model or revision')
                self._cached, self._stamp = cached, stamp
            cached = self._cached
            chunks = cached["chunks"]
            vectors = [normalized(row) for row in cached["vectors"]]
            if len(chunks) != len(vectors):
                raise ValueError("RAG index is incomplete; run build_index")
            vector = normalized(self.encoder.encode([query])[0]) if chunks else []
            if not chunks:
                return []
            if any(len(row) != len(vector) for row in vectors):
                raise ValueError("Inconsistent query embedding dimensions")
            ranked = []
            for chunk, row in zip(chunks, vectors):
                # Recheck immediately before exposing each cached result.
                if self.vault.policy.evaluate("read", chunk["path"]).decision == "block":
                    continue
                if not self.vault.note_path(chunk['path']).is_file():
                    continue
                score = sum(a * b for a, b in zip(row, vector))
                ranked.append(dict(chunk, score=score))
            ranked.sort(key=lambda item: (-item["score"], item["path"], item["start"]))
            result, seen = [], set()
            for hit in ranked:
                if hit["path"] not in seen:
                    result.append(hit)
                    seen.add(hit["path"])
                    if len(result) == limit:
                        break
            return result
