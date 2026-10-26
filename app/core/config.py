"""Central configuration for the small Hello-Agents learning framework."""

import os
from typing import Any, Optional

from pydantic import BaseModel


class Config(BaseModel):
    """Agent and LLM configuration, with environment-variable overrides."""

    # LLM configuration
    default_model: str = "qwen3.5-plus"
    default_provider: str = "dashscope"
    default_protocol: str = "openai_compatible"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # System configuration
    debug: bool = False
    log_level: str = "INFO"

    # Conversation configuration
    max_history_length: int = 100

    @classmethod
    def from_env(cls) -> "Config":
        """Create a Config, overriding defaults with supported environment variables."""
        debug_value = os.getenv("DEBUG", "false").strip().lower()
        max_tokens_value = os.getenv("MAX_TOKENS")

        return cls(
            default_model=os.getenv("LLM_MODEL_ID", "qwen3.5-plus"),
            default_provider=os.getenv("LLM_PROVIDER", "dashscope"),
            default_protocol=os.getenv("LLM_PROTOCOL", "openai_compatible"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(max_tokens_value) if max_tokens_value else None,
            debug=debug_value in {"true", "1", "yes"},
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_history_length=int(os.getenv("MAX_HISTORY_LENGTH", "100")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the configuration fields (without unrelated Message fields)."""
        return self.model_dump()
