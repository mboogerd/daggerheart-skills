from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JudgeResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    passed: bool = Field(alias="pass")
    score: int = Field(ge=1, le=5)
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    def as_payload(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)


def judge_with_pydantic_ai(*, provider: str, model: str, prompt: str) -> tuple[dict[str, object], dict[str, object]]:
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.models.openai import OpenAIResponsesModel

    if provider == "claude":
        provider_model = AnthropicModel(model)
        provider_model_name = f"anthropic:{model}"
    elif provider == "codex":
        provider_model = OpenAIResponsesModel(model)
        provider_model_name = f"openai-responses:{model}"
    else:
        raise ValueError(f"Unsupported judge provider: {provider}")

    agent = Agent(
        provider_model,
        instructions=(
            "You are a strict repository evaluation judge. "
            "Read the provided user request and verification properties, then return only the structured judgment."
        ),
        output_type=JudgeResult,
    )

    result = agent.run_sync(prompt)
    payload = result.output.as_payload()
    metadata = {
        "provider": provider,
        "model": model,
        "pydantic_ai_model": provider_model_name,
    }
    return payload, metadata
