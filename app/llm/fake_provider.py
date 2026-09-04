"""Deterministic offline provider for tests and local development without API keys.

Structured completions return a schema-default instance unless a handler is registered for
that schema. Embeddings are hashed bag-of-words vectors, so similar texts still rank close.
"""

import hashlib
import math
import re
from collections.abc import Callable

from pydantic import BaseModel

from app.llm.base import LLMProvider

Handler = Callable[[str, str], BaseModel]


class FakeProvider(LLMProvider):
    name = "fake"
    chat_model = "fake-chat"
    embedding_model = "fake-embed"

    def __init__(self, embedding_dim: int = 768, handlers: dict[type[BaseModel], Handler] | None = None):
        self.embedding_dim = embedding_dim
        self.handlers = handlers or {}

    def complete_structured(self, system, user, schema):
        handler = self.handlers.get(schema)
        if handler:
            return handler(system, user)
        return schema()

    def _complete_json(self, messages, schema):  # pragma: no cover - not used
        return "{}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.embedding_dim
        for tok in re.findall(r"[a-z0-9+#.]+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.embedding_dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
