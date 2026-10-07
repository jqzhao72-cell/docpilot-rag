"""DeepSeek client used by the DocPilot answer pipeline."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class DeepSeekLLM:
    """Generate grounded answers through the OpenAI-compatible DeepSeek API."""

    def __init__(
        self,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "DEEPSEEK_API_KEY is not set; configure it in the environment or .env"
            )
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate(self, prompt: str) -> str:
        """Return one grounded answer for a fully constructed RAG prompt."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are DocPilot. Use only the supplied contexts as evidence, "
                        "never fabricate sources, and cite evidence with [1], [2], etc."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        answer = response.choices[0].message.content
        return answer.strip() if answer else ""
