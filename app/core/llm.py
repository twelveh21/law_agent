"""A small OpenAI-compatible LLM client used by the Hello-Agents exercises."""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from .config import Config


# Load local development settings before resolving credentials.
load_dotenv()


class law_llm:
    """Call an OpenAI-compatible chat-completions endpoint such as DashScope."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.config = config or Config.from_env()
        self.model = model or self.config.default_model
        self.provider = self.config.default_provider.strip().lower()

        if self.config.default_protocol != "openai_compatible":
            raise ValueError(
                "当前 HelloAgentsLLM 只实现了 openai_compatible 协议"
            )

        # OpenAI is the client library/protocol adapter here; the endpoint and
        # credentials determine which service actually receives the request.
        if self.provider == "dashscope":
            provider_prefix = "DASHSCOPE"
        elif self.provider == "openai":
            provider_prefix = "OPENAI"
        else:
            raise ValueError(
                f"暂不支持 provider={self.provider!r}，目前支持 dashscope/openai"
            )

        resolved_api_key = (
            api_key
            or os.getenv(f"{provider_prefix}_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        resolved_base_url = (
            base_url
            or os.getenv(f"{provider_prefix}_BASE_URL")
            or os.getenv("LLM_BASE_URL")
        )

        if self.provider == "openai" and not resolved_base_url:
            resolved_base_url = "https://api.openai.com/v1"

        if not resolved_api_key:
            raise ValueError(
                f"缺少 API Key，请设置 {provider_prefix}_API_KEY 或 LLM_API_KEY"
            )
        if not resolved_base_url:
            raise ValueError(
                f"缺少 Base URL，请设置 {provider_prefix}_BASE_URL 或 LLM_BASE_URL"
            )

        resolved_timeout = (
            timeout if timeout is not None else int(os.getenv("LLM_TIMEOUT", "60"))
        )

        self.client = OpenAI(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            timeout=resolved_timeout,
        )

    def think(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """Send chat messages and return the complete streamed response text."""
        request_temperature = (
            self.config.temperature if temperature is None else temperature
        )

        print(f"正在调用模型：{self.model}")
        collected_content: list[str] = []

        try:
            response_stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=request_temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
            )

            for chunk in response_stream:
                if not chunk.choices:
                    continue

                content = chunk.choices[0].delta.content
                if isinstance(content, str):
                    collected_content.append(content)
                    print(content, end="", flush=True)

            print()
            return "".join(collected_content)

        except Exception as exc:
            print(f"调用 LLM API 时发生错误：{exc}")
            return None
