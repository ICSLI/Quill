"""
프롬프트 템플릿 관리자

프롬프트 템플릿을 로드하고, ChatML 파싱 및 변수 치환을 처리합니다.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from core.chatml_parser import ChatMLParser


logger = logging.getLogger(__name__)


class PromptManager:
    """프롬프트 템플릿 관리자"""

    def __init__(self, prompts_path: Optional[str] = None):
        """
        PromptManager 초기화

        Args:
            prompts_path: 프롬프트 파일 경로
                         (기본값: resources/default_prompts.json)
        """
        if prompts_path is None:
            # 프로젝트 루트 기준 resources/default_prompts.json
            project_root = Path(__file__).parent.parent
            prompts_path = project_root / "resources" / "default_prompts.json"

        self.prompts_path = Path(prompts_path)
        self.prompts: Dict[str, Dict[str, Any]] = {}
        self.parser = ChatMLParser()

        logger.debug(f"PromptManager initialized with path: {self.prompts_path}")

        # 프롬프트 로드
        self.load()

    def load(self) -> None:
        """
        프롬프트 파일 로드

        Raises:
            FileNotFoundError: 프롬프트 파일이 존재하지 않는 경우
            json.JSONDecodeError: JSON 파싱 실패 시
        """
        if not self.prompts_path.exists():
            logger.error(f"Prompts file not found: {self.prompts_path}")
            raise FileNotFoundError(f"Prompts file not found: {self.prompts_path}")

        try:
            with open(self.prompts_path, 'r', encoding='utf-8') as f:
                self.prompts = json.load(f)
            logger.info(f"Loaded {len(self.prompts)} prompts from {self.prompts_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in prompts file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading prompts: {e}")
            raise

    def get_prompt_keys(self) -> List[str]:
        """
        사용 가능한 프롬프트 키 목록

        Returns:
            프롬프트 키 리스트
        """
        return list(self.prompts.keys())

    def get_prompt_info(self, prompt_key: str) -> Optional[Dict[str, Any]]:
        """
        프롬프트 정보 가져오기

        Args:
            prompt_key: 프롬프트 키

        Returns:
            프롬프트 정보 딕셔너리 (name, template, temperature)
        """
        return self.prompts.get(prompt_key)

    def get_messages(
        self,
        prompt_key: str,
        text: str,
        instruction: str = ""
    ) -> List[Dict[str, str]]:
        """
        프롬프트 템플릿을 OpenAI messages 형식으로 변환

        Args:
            prompt_key: 프롬프트 키 (예: "grammar_check")
            text: 선택된 텍스트
            instruction: 사용자 지시사항 (선택적)

        Returns:
            OpenAI messages 형식의 리스트

        Raises:
            ValueError: 존재하지 않는 프롬프트 키
        """
        prompt_info = self.get_prompt_info(prompt_key)
        if not prompt_info:
            logger.error(f"Unknown prompt key: {prompt_key}")
            raise ValueError(f"Unknown prompt key: {prompt_key}")

        template = prompt_info["template"]

        # 변수 준비
        variables = {
            "text": text,
            "instruction": instruction
        }

        # ChatML 파싱 + 변수 치환
        messages = self.parser.parse_and_substitute(template, variables)
        logger.debug(f"Generated {len(messages)} messages for prompt: {prompt_key}")

        return messages

    def get_temperature(self, prompt_key: str) -> float:
        """
        프롬프트의 temperature 값 가져오기

        Args:
            prompt_key: 프롬프트 키

        Returns:
            temperature 값 (기본값: 0.7)
        """
        prompt_info = self.get_prompt_info(prompt_key)
        if not prompt_info:
            return 0.7

        return prompt_info.get("temperature", 0.7)

    def add_prompt(
        self,
        prompt_key: str,
        name: str,
        template: str,
        temperature: float = 0.7
    ) -> None:
        """
        새 프롬프트 추가

        Args:
            prompt_key: 프롬프트 키
            name: 프롬프트 이름
            template: ChatML 템플릿
            temperature: temperature 값
        """
        self.prompts[prompt_key] = {
            "name": name,
            "template": template,
            "temperature": temperature
        }
        logger.info(f"Added prompt: {prompt_key}")

    def update_prompt(
        self,
        prompt_key: str,
        name: Optional[str] = None,
        template: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> None:
        """
        기존 프롬프트 업데이트

        Args:
            prompt_key: 프롬프트 키
            name: 새 이름 (None이면 유지)
            template: 새 템플릿 (None이면 유지)
            temperature: 새 temperature (None이면 유지)

        Raises:
            ValueError: 존재하지 않는 프롬프트 키
        """
        if prompt_key not in self.prompts:
            raise ValueError(f"Unknown prompt key: {prompt_key}")

        if name is not None:
            self.prompts[prompt_key]["name"] = name
        if template is not None:
            self.prompts[prompt_key]["template"] = template
        if temperature is not None:
            self.prompts[prompt_key]["temperature"] = temperature

        logger.info(f"Updated prompt: {prompt_key}")

    def save(self, save_path: Optional[str] = None) -> None:
        """
        프롬프트를 파일에 저장

        Args:
            save_path: 저장 경로 (기본값: 현재 prompts_path)

        Raises:
            OSError: 파일 쓰기 실패 시
        """
        if save_path is None:
            save_path = self.prompts_path

        save_path = Path(save_path)

        # 디렉토리가 없으면 생성
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, indent=2, ensure_ascii=False)
            logger.info(f"Prompts saved to {save_path}")
        except Exception as e:
            logger.error(f"Error saving prompts: {e}")
            raise


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing PromptManager ===\n")

    # PromptManager 생성
    pm = PromptManager()

    # 1. 프롬프트 목록 확인
    print("1. Available prompts:")
    for key in pm.get_prompt_keys():
        info = pm.get_prompt_info(key)
        print(f"   - {key}: {info['name']} (temp={info['temperature']})")

    # 2. 문법 검사 프롬프트 생성
    print("\n2. Testing grammar_check prompt...")
    text = "I are student and you is teacher."
    messages = pm.get_messages("grammar_check", text)
    print(f"   Generated {len(messages)} messages:")
    for msg in messages:
        print(f"   [{msg['role']}]: {msg['content'][:50]}...")

    # 3. 재작성 프롬프트 (instruction 포함)
    print("\n3. Testing rewrite prompt with instruction...")
    text = "The cat sat on the mat."
    instruction = "Make it more dramatic and exciting"
    messages = pm.get_messages("rewrite", text, instruction)
    print(f"   Generated {len(messages)} messages")
    print(f"   User message includes instruction: {instruction in messages[1]['content']}")
    print(f"   User message includes text: {text in messages[1]['content']}")

    # 4. Temperature 확인
    print("\n4. Testing temperature values...")
    print(f"   grammar_check: {pm.get_temperature('grammar_check')}")
    print(f"   rewrite: {pm.get_temperature('rewrite')}")
    print(f"   summarize: {pm.get_temperature('summarize')}")

    # 5. 커스텀 프롬프트 추가
    print("\n5. Testing custom prompt addition...")
    pm.add_prompt(
        "test_custom",
        "Test Custom",
        "<|im_start|>system\nTest system message\n<|im_end|>\n<|im_start|>user\n{{text}}\n<|im_end|>",
        temperature=0.5
    )
    assert "test_custom" in pm.get_prompt_keys()
    print("   [OK] Custom prompt added")

    print("\n[OK] All PromptManager tests passed!")
