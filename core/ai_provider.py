"""
OAI Compatible API Provider

OpenAI Chat Completions API 호환 엔드포인트를 호출합니다.
OpenAI, llama.cpp, KoboldCPP, Ollama 등 모든 호환 서비스 지원.
"""

import logging
from typing import List, Dict, Any, Optional

import httpx


logger = logging.getLogger(__name__)


class OAICompatibleProvider:
    """OpenAI Compatible API Provider"""

    def __init__(self):
        """OAICompatibleProvider 초기화"""
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.model: str = "gpt-4"
        self.client: Optional[httpx.Client] = None
        self.timeout: float = 60.0  # 60초 타임아웃

        logger.debug("OAICompatibleProvider initialized")

    def configure(self, base_url: str, api_key: str, model: str) -> None:
        """
        API 설정

        Args:
            base_url: API base URL (예: https://api.openai.com/v1)
            api_key: API 키
            model: 모델 이름 (예: gpt-4, gpt-3.5-turbo)
        """
        # 기존 클라이언트 정리 (연결 누수 방지)
        if self.client is not None:
            try:
                self.client.close()
                logger.debug("Previous httpx client closed")
            except Exception as e:
                logger.warning(f"Error closing previous client: {e}")
            self.client = None

        # URL 정규화 (끝에 슬래시 제거)
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model

        # httpx 클라이언트 초기화
        headers = {
            "Content-Type": "application/json"
        }

        # API 키가 있으면 Authorization 헤더 추가
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout
        )

        logger.info(f"Configured API: {self.base_url}, model: {self.model}")

    def is_configured(self) -> bool:
        """
        API가 설정되어 있는지 확인

        Returns:
            설정 완료 여부
        """
        return self.client is not None

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        채팅 완성 API 호출 (비스트리밍)

        Args:
            messages: OpenAI messages 형식
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "..."}]
            temperature: 온도 (0.0~2.0, 기본값 0.7)
            max_tokens: 최대 토큰 수 (None이면 제한 없음)
            additional_params: 추가 파라미터 (reasoning_effort, top_p 등)

        Returns:
            AI 응답 텍스트

        Raises:
            RuntimeError: API 호출 실패 시
            ValueError: API 미설정 시
        """
        if not self.is_configured():
            raise ValueError("API provider not configured. Call configure() first.")

        try:
            # 요청 페이로드 구성
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": False  # 비스트리밍
            }

            if max_tokens is not None:
                payload["max_tokens"] = max_tokens

            # 추가 파라미터 병합
            if additional_params:
                payload.update(additional_params)

            logger.debug(f"Calling API: {self.base_url}/chat/completions")
            logger.debug(f"Model: {self.model}, messages count: {len(messages)}")

            # API 호출
            response = self.client.post(
                "/chat/completions",
                json=payload
            )

            # HTTP 에러 확인
            response.raise_for_status()

            # 응답 파싱
            data = response.json()

            if "choices" not in data or len(data["choices"]) == 0:
                logger.error(f"Invalid API response: {data}")
                raise RuntimeError("Invalid API response: no choices")

            content = data["choices"][0]["message"]["content"]
            logger.info(f"API call successful, response length: {len(content)}")

            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            error_detail = self._extract_error_message(e.response)
            raise RuntimeError(f"API error ({e.response.status_code}): {error_detail}") from e

        except httpx.TimeoutException as e:
            logger.error(f"API request timeout: {e}")
            raise RuntimeError("API request timeout") from e

        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise RuntimeError(f"Request error: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise RuntimeError(f"Unexpected error: {e}") from e

    def test_connection(self) -> bool:
        """
        API 연결 테스트

        Returns:
            연결 성공 여부
        """
        if not self.is_configured():
            logger.warning("Cannot test connection: API not configured")
            return False

        try:
            logger.info("Testing API connection...")
            test_messages = [
                {"role": "user", "content": "Hi"}
            ]

            response = self.complete(test_messages, temperature=0.1)
            logger.info("Connection test successful")
            return True

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def close(self) -> None:
        """API 클라이언트 종료"""
        if self.client:
            self.client.close()
            logger.debug("API client closed")

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """
        에러 응답에서 메시지 추출

        Args:
            response: httpx Response 객체

        Returns:
            에러 메시지
        """
        try:
            error_data = response.json()
            if "error" in error_data:
                if isinstance(error_data["error"], dict):
                    return error_data["error"].get("message", str(error_data["error"]))
                else:
                    return str(error_data["error"])
            return response.text
        except Exception:
            return response.text

    def __del__(self):
        """소멸자: 자동으로 클라이언트 종료"""
        self.close()


# 테스트 코드
if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing OAICompatibleProvider ===\n")

    # 환경 변수에서 API 키 가져오기 (테스트용)
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        print("[WARNING] OPENAI_API_KEY environment variable not set")
        print("   Set it to test the provider:")
        print("   export OPENAI_API_KEY=your-api-key")
        print("\nTesting with mock configuration instead...")

        # Mock 설정 테스트
        provider = OAICompatibleProvider()
        assert not provider.is_configured()
        print("[OK] Initial state: not configured")

        provider.configure(
            base_url="https://api.openai.com/v1",
            api_key="sk-test-mock-key",
            model="gpt-4"
        )
        assert provider.is_configured()
        print("[OK] Configuration successful")

        print("\n[INFO] Skipping actual API call (no real API key)")
        print("[OK] Basic tests passed!")

    else:
        # 실제 API 테스트
        provider = OAICompatibleProvider()
        provider.configure(
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            model="gpt-3.5-turbo"  # 저렴한 모델로 테스트
        )

        print("1. Testing simple completion...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
        ]

        try:
            response = provider.complete(messages, temperature=0.1)
            print(f"   Response: {response}")
            print("   [OK] Completion test passed!")

        except Exception as e:
            print(f"   [FAILED] {e}")

        print("\n2. Testing connection...")
        if provider.test_connection():
            print("   [OK] Connection test passed!")
        else:
            print("   [FAILED] Connection test failed!")

        provider.close()

    print("\n[OK] All provider tests completed!")
