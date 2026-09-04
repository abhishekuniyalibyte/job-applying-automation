import json
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    """Minimal abstraction so OpenAI / Gemini / a fake can be swapped without touching services."""

    name: str = "base"
    chat_model: str = ""
    embedding_model: str = ""
    max_attempts: int = 2

    @abstractmethod
    def _complete_json(self, messages: list[dict], schema: type[BaseModel]) -> str:
        """Return raw JSON text for the given chat messages."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    def complete_structured(self, system: str, user: str, schema: type[T]) -> T:
        schema_json = json.dumps(schema.model_json_schema(), indent=0)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system}\n\nRespond ONLY with a single JSON object that validates against this JSON schema. "
                    f"Do not wrap it in markdown.\n{schema_json}"
                ),
            },
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        for _ in range(self.max_attempts):
            text = self._complete_json(messages, schema)
            try:
                return schema.model_validate_json(_strip_fences(text))
            except ValidationError as err:
                last_err = err
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {
                        "role": "user",
                        "content": f"That JSON failed validation:\n{err}\nReturn a corrected JSON object only.",
                    }
                )
        raise LLMError(f"{self.name}: structured output failed validation: {last_err}")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()
