from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(s.openai_api_key, s.openai_chat_model, s.openai_embedding_model, s.embedding_dim)
    if s.llm_provider == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(s.gemini_api_key, s.gemini_chat_model, s.gemini_embedding_model, s.embedding_dim)
    from app.llm.fake_provider import FakeProvider

    return FakeProvider(embedding_dim=s.embedding_dim)
