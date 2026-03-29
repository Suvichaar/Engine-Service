"""Azure OpenAI client for language model completion."""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.services.model_clients import LanguageModel


class AzureOpenAILanguageModel(LanguageModel):
    """Azure OpenAI implementation of LanguageModel protocol."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = "2024-02-15-preview",
        timeout: float = 60.0,
        max_retries: int = 3,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._deployment = deployment
        self._api_version = api_version
        self._timeout = timeout
        self._max_retries = max_retries
        self._logger = logger or logging.getLogger(__name__)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Generate completion using Azure OpenAI chat API."""
        url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"
        params = {"api-version": self._api_version}
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        for attempt in range(self._max_retries):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(url, headers=headers, params=params, json=payload)
                    response.raise_for_status()
                    data = response.json()

                    # Extract content from response
                    choices = data.get("choices", [])
                    if choices and choices[0].get("message"):
                        content = choices[0]["message"].get("content", "")
                        if content:
                            return content.strip()

                    self._logger.warning("Azure OpenAI: empty response content")
                    return "No content generated."

            except httpx.HTTPStatusError as e:
                self._logger.error(
                    "Azure OpenAI API error (attempt %d/%d): %s", attempt + 1, self._max_retries, e
                )
                if attempt == self._max_retries - 1:
                    raise
                # Exponential backoff
                time.sleep(2 ** attempt)
            except httpx.RequestError as e:
                self._logger.error(
                    "Azure OpenAI network error (attempt %d/%d): %s", attempt + 1, self._max_retries, e
                )
                if attempt == self._max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except Exception as e:
                self._logger.error("Unexpected error in Azure OpenAI: %s", e)
                if attempt == self._max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return "Error: Failed to generate content after retries."


__all__ = ["AzureOpenAILanguageModel"]

