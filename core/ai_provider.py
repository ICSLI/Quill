"""Synchronous client for OpenAI-compatible Chat Completions endpoints."""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)
RESERVED_PARAMS = frozenset({"model", "messages", "stream"})


def validate_api_url(base_url: str) -> str:
    """Return a normalized HTTP(S) base URL or raise a useful input error."""
    if not isinstance(base_url, str):
        raise ValueError("Base URL must be a string")
    value = base_url.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        # Accessing port also validates malformed/out-of-range ports.
        parsed.port
    except ValueError as exc:
        raise ValueError("Base URL has an invalid host or port") from exc
    if (not valid or any(character.isspace() for character in value)
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or "?" in value or "#" in value):
        raise ValueError("Base URL must be an HTTP(S) URL without credentials, query, or fragment")
    return value


class OAICompatibleProvider:
    """Reuse one HTTP connection pool for a configured API endpoint."""

    def __init__(self):
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.model: str = "gpt-4"
        self.client: Optional[httpx.Client] = None
        self.timeout: float = 60.0

    def configure(self, base_url: str, api_key: str, model: str) -> None:
        base_url = validate_api_url(base_url)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model cannot be empty")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        # Construct first so invalid new settings do not destroy a working client.
        client = httpx.Client(base_url=base_url, headers=headers, timeout=self.timeout)
        self.close()
        self.base_url, self.api_key, self.model = base_url, api_key, model.strip()
        self.client = client
        logger.info("Configured API endpoint, model: %s", self.model)

    def is_configured(self) -> bool:
        return self.client is not None and not self.client.is_closed

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self.is_configured():
            raise ValueError("API provider not configured. Call configure() first.")
        if additional_params is not None and not isinstance(additional_params, dict):
            raise ValueError("Additional parameters must be a JSON object")
        if additional_params and RESERVED_PARAMS.intersection(additional_params):
            raise ValueError("Additional parameters cannot override model, messages, or stream")
        payload = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if additional_params:
            payload.update(additional_params)

        try:
            response = self.client.post("chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise RuntimeError("Invalid API response: no completion choices")
            choice = choices[0]
            # Never replace a selection with a truncated/refused answer.
            if choice.get("finish_reason") in {"length", "content_filter"}:
                raise RuntimeError("API response was truncated or filtered; original text was preserved")
            message = choice.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("API response contains no usable text; original text was preserved")
            logger.info("API call successful, response length: %s", len(content))
            return content
        except httpx.HTTPStatusError as exc:
            # Error responses can echo the selected text, so do not log the body.
            logger.warning("API HTTP error: %s", exc.response.status_code)
            detail = self._extract_error_message(exc.response)
            raise RuntimeError(f"API error ({exc.response.status_code}): {detail}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("API request timeout") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"API connection failed ({type(exc).__name__})") from exc
        except (ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("Invalid API response: expected a JSON text completion") from exc

    def test_connection(self) -> bool:
        if not self.is_configured():
            return False
        try:
            self.complete([{"role": "user", "content": "Hi"}], temperature=0.1)
            return True
        except Exception:
            logger.warning("API connection test failed")
            return False

    def close(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            client.close()

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                return str(error.get("message", "Unknown API error"))[:500]
            if isinstance(error, str):
                return error[:500]
        except ValueError:
            pass
        return response.reason_phrase or "Unknown API error"

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
