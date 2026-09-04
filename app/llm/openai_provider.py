from pydantic import BaseModel

from app.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, chat_model: str, embedding_model: str, embedding_dim: int):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim

    def _complete_json(self, messages: list[dict], schema: type[BaseModel]) -> str:
        resp = self.client.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content or "{}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            resp = self.client.embeddings.create(
                model=self.embedding_model, input=batch, dimensions=self.embedding_dim
            )
            out.extend([d.embedding for d in resp.data])
        return out
