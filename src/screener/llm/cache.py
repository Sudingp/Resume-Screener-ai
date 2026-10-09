"""Content-addressed disk cache for LLM extraction results."""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional
from screener.models import ResumeExtraction


class LLMCache:
    """Disk cache keyed by sha256(model + prompt_version + schema_version + text_hash)."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            cache_dir = base_dir / ".cache" / "llm"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(
        self,
        model: str,
        prompt_version: str,
        schema_version: str,
        text_hash: str,
    ) -> str:
        raw = f"{model}:{prompt_version}:{schema_version}:{text_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        model: str,
        prompt_version: str,
        schema_version: str,
        text_hash: str,
    ) -> Optional[ResumeExtraction]:
        """Retrieve cached extraction if present and valid."""
        key = self._make_key(model, prompt_version, schema_version, text_hash)
        path = self.cache_dir / f"{key}.json"

        if not path.is_file():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ResumeExtraction.model_validate(data)
        except Exception:
            # Corrupt cache entry: ignore safely
            return None

    def set(
        self,
        model: str,
        prompt_version: str,
        schema_version: str,
        text_hash: str,
        extraction: ResumeExtraction,
    ) -> None:
        """Atomically write extraction to cache."""
        key = self._make_key(model, prompt_version, schema_version, text_hash)
        target_path = self.cache_dir / f"{key}.json"
        tmp_path = self.cache_dir / f"{key}.tmp.{os.getpid()}"

        try:
            content = extraction.model_dump_json(indent=2)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, target_path)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
