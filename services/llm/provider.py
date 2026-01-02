"""LLM Provider abstraction layer."""
import json
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger()


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat message and get a response."""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response."""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get text completion."""
        pass

    async def health_check(self) -> bool:
        """Check if the provider is available."""
        try:
            await self.chat(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False


class LMStudioProvider(BaseLLMProvider):
    """LM Studio provider for local LLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "local-model",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat message to LM Studio."""
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            return {
                "id": data.get("id", ""),
                "model": data.get("model", self.model),
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }

        except httpx.HTTPError as e:
            logger.error("LM Studio request failed", error=str(e))
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from LM Studio."""
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error("LM Studio stream failed", error=str(e))
            raise

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get text completion from LM Studio."""
        # Use chat API for completion
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return {
            "id": result["id"],
            "model": result["model"],
            "text": result["content"],
            "usage": result["usage"],
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider for production LLM inference."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.client = httpx.AsyncClient(timeout=timeout)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert OpenAI-style messages to Gemini format."""
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        return contents, system_instruction

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat message to Gemini."""
        contents, system_instruction = self._convert_messages(messages)

        request_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            response = await self.client.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

            content = ""
            if "candidates" in data and data["candidates"]:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                content = "".join(part.get("text", "") for part in parts)

            return {
                "id": f"gemini-{self.model}",
                "model": self.model,
                "content": content,
                "usage": data.get("usageMetadata", {}),
            }

        except httpx.HTTPError as e:
            logger.error("Gemini request failed", error=str(e))
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream chat response from Gemini."""
        contents, system_instruction = self._convert_messages(messages)

        request_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/models/{self.model}:streamGenerateContent",
                params={"key": self.api_key, "alt": "sse"},
                json=request_body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if "candidates" in data and data["candidates"]:
                                parts = data["candidates"][0].get("content", {}).get("parts", [])
                                for part in parts:
                                    text = part.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error("Gemini stream failed", error=str(e))
            raise

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Get text completion from Gemini."""
        result = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return {
            "id": result["id"],
            "model": result["model"],
            "text": result["content"],
            "usage": result["usage"],
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class FallbackProvider(BaseLLMProvider):
    """Provider that tries multiple providers in order."""

    def __init__(self, providers: List[BaseLLMProvider]):
        self.providers = providers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Try each provider until one succeeds."""
        last_error = None
        for provider in self.providers:
            try:
                return await provider.chat(messages, temperature, max_tokens, **kwargs)
            except Exception as e:
                logger.warning(
                    "Provider failed, trying next",
                    provider=type(provider).__name__,
                    error=str(e),
                )
                last_error = e
        raise last_error or Exception("All providers failed")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Try each provider until one succeeds."""
        last_error = None
        for provider in self.providers:
            try:
                async for chunk in provider.chat_stream(
                    messages, temperature, max_tokens, **kwargs
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(
                    "Provider stream failed, trying next",
                    provider=type(provider).__name__,
                    error=str(e),
                )
                last_error = e
        raise last_error or Exception("All providers failed")

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> Dict[str, Any]:
        """Try each provider until one succeeds."""
        last_error = None
        for provider in self.providers:
            try:
                return await provider.complete(prompt, temperature, max_tokens, **kwargs)
            except Exception as e:
                logger.warning(
                    "Provider failed, trying next",
                    provider=type(provider).__name__,
                    error=str(e),
                )
                last_error = e
        raise last_error or Exception("All providers failed")


# Global provider instance
_provider: Optional[BaseLLMProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    """Get the configured LLM provider."""
    global _provider

    if _provider is None:
        from app.config import settings

        providers = []

        # Add Gemini if configured
        if settings.gemini_api_key:
            providers.append(
                GeminiProvider(
                    api_key=settings.gemini_api_key,
                    model="gemini-pro",
                )
            )

        # Add LM Studio for local development
        if settings.lmstudio_base_url:
            providers.append(
                LMStudioProvider(
                    base_url=settings.lmstudio_base_url,
                )
            )

        if not providers:
            raise ValueError("No LLM provider configured")

        # Use primary provider based on environment
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            _provider = FallbackProvider(
                [p for p in providers if isinstance(p, GeminiProvider)]
                + [p for p in providers if isinstance(p, LMStudioProvider)]
            )
        else:
            _provider = FallbackProvider(
                [p for p in providers if isinstance(p, LMStudioProvider)]
                + [p for p in providers if isinstance(p, GeminiProvider)]
            )

    return _provider

