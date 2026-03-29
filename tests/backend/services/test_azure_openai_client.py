"""Tests for Azure OpenAI client."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, Mock, patch

import httpx
import pytest

from app.services.azure_openai_client import AzureOpenAILanguageModel


class TestAzureOpenAILanguageModel:
    """Test suite for AzureOpenAILanguageModel."""

    def test_initialization(self):
        """Test client initialization with parameters."""
        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            api_version="2024-02-15-preview",
            timeout=30.0,
            max_retries=2,
        )

        assert client._endpoint == "https://test.openai.azure.com"
        assert client._api_key == "test-key"
        assert client._deployment == "gpt-4"
        assert client._api_version == "2024-02-15-preview"
        assert client._timeout == 30.0
        assert client._max_retries == 2

    def test_endpoint_strips_trailing_slash(self):
        """Test that endpoint trailing slash is removed."""
        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            deployment="gpt-4",
        )
        assert client._endpoint == "https://test.openai.azure.com"

    @patch("httpx.Client")
    def test_complete_success(self, mock_client_class):
        """Test successful completion request."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This is the generated response."
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        # Mock client
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Create client and call
        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
        )

        result = client.complete("You are a helpful assistant.", "Tell me about AI.")

        assert result == "This is the generated response."
        mock_client.post.assert_called_once()
        
        # Verify URL construction
        call_args = mock_client.post.call_args
        assert "/openai/deployments/gpt-4/chat/completions" in call_args[0][0]
        
        # Verify headers
        assert call_args[1]["headers"]["api-key"] == "test-key"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        
        # Verify payload
        payload = call_args[1]["json"]
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are a helpful assistant."
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == "Tell me about AI."
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2000

    @patch("httpx.Client")
    def test_complete_strips_whitespace(self, mock_client_class):
        """Test that response content is stripped of whitespace."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "  Response with spaces  \n"
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
        )

        result = client.complete("system", "user")

        assert result == "Response with spaces"

    @patch("httpx.Client")
    def test_complete_empty_response(self, mock_client_class):
        """Test handling of empty response content."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
        )

        result = client.complete("system", "user")

        assert result == "No content generated."

    @patch("httpx.Client")
    def test_complete_no_choices(self, mock_client_class):
        """Test handling of response with no choices."""
        mock_response = Mock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
        )

        result = client.complete("system", "user")

        assert result == "No content generated."

    @patch("httpx.Client")
    def test_complete_retries_on_http_error(self, mock_client_class):
        """Test retry logic on HTTP status errors."""
        # First two calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(),
            response=Mock(status_code=500)
        )

        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success after retry"}}]
        }
        mock_response_success.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            max_retries=3,
        )

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = client.complete("system", "user")

        assert result == "Success after retry"
        assert mock_client.post.call_count == 3

    @patch("httpx.Client")
    def test_complete_raises_after_max_retries(self, mock_client_class):
        """Test that exception is raised after max retries."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(),
            response=Mock(status_code=500)
        )

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            max_retries=2,
        )

        with patch("time.sleep"):  # Mock sleep to speed up test
            with pytest.raises(httpx.HTTPStatusError):
                client.complete("system", "user")

        assert mock_client.post.call_count == 2

    @patch("httpx.Client")
    def test_complete_retries_on_network_error(self, mock_client_class):
        """Test retry logic on network errors."""
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success after network retry"}}]
        }
        mock_response_success.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.side_effect = [
            httpx.RequestError("Network error", request=Mock()),
            mock_response_success
        ]
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            max_retries=3,
        )

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = client.complete("system", "user")

        assert result == "Success after network retry"
        assert mock_client.post.call_count == 2

    @patch("httpx.Client")
    def test_complete_retries_on_general_exception(self, mock_client_class):
        """Test retry logic on general exceptions."""
        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            "choices": [{"message": {"content": "Success after exception"}}]
        }
        mock_response_success.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.side_effect = [
            ValueError("Unexpected error"),
            mock_response_success
        ]
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            max_retries=3,
        )

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = client.complete("system", "user")

        assert result == "Success after exception"
        assert mock_client.post.call_count == 2

    @patch("httpx.Client")
    def test_complete_exponential_backoff(self, mock_client_class):
        """Test that exponential backoff is used between retries."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=Mock(),
            response=Mock(status_code=500)
        )

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            max_retries=3,
        )

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(httpx.HTTPStatusError):
                client.complete("system", "user")

        # Verify exponential backoff: 2^0, 2^1 = 1, 2 seconds
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # 2^0 = 1
        mock_sleep.assert_any_call(2)  # 2^1 = 2

    @patch("httpx.Client")
    def test_complete_api_version_in_params(self, mock_client_class):
        """Test that API version is included in query parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            api_version="2024-02-15-preview",
        )

        client.complete("system", "user")

        call_args = mock_client.post.call_args
        assert call_args[1]["params"]["api-version"] == "2024-02-15-preview"

    @patch("httpx.Client")
    def test_complete_timeout_set(self, mock_client_class):
        """Test that timeout is set on httpx client."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = AzureOpenAILanguageModel(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="gpt-4",
            timeout=45.0,
        )

        client.complete("system", "user")

        # Verify httpx.Client was called with timeout
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["timeout"] == 45.0

