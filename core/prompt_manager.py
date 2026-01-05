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

    def __init__(self, prompts_path: Optional[str] = None, user_prompts_path: Optional[str] = None):
        """
        PromptManager 초기화

        Args:
            prompts_path: 기본 프롬프트 파일 경로
                         (기본값: resources/default_prompts.json)
            user_prompts_path: 사용자 프롬프트 파일 경로
                              (기본값: data/user_prompts.json)
        """
        project_root = Path(__file__).parent.parent

        if prompts_path is None:
            prompts_path = project_root / "resources" / "default_prompts.json"
        if user_prompts_path is None:
            user_prompts_path = project_root / "data" / "user_prompts.json"

        self.prompts_path = Path(prompts_path)
        self.user_prompts_path = Path(user_prompts_path)

        self.default_prompts: Dict[str, Dict[str, Any]] = {}
        self.user_prompts: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, Any]] = {}  # 병합된 프롬프트
        self.parser = ChatMLParser()

        logger.debug(f"PromptManager initialized")
        logger.debug(f"  Default prompts: {self.prompts_path}")
        logger.debug(f"  User prompts: {self.user_prompts_path}")

        # 프롬프트 로드
        self.load()

    def load(self) -> None:
        """
        프롬프트 파일 로드 (기본 + 사용자 프롬프트 병합)

        Raises:
            FileNotFoundError: 기본 프롬프트 파일이 존재하지 않는 경우
            json.JSONDecodeError: JSON 파싱 실패 시
        """
        # 1. 기본 프롬프트 로드 (필수)
        if not self.prompts_path.exists():
            logger.error(f"Default prompts file not found: {self.prompts_path}")
            raise FileNotFoundError(f"Default prompts file not found: {self.prompts_path}")

        try:
            with open(self.prompts_path, 'r', encoding='utf-8') as f:
                self.default_prompts = json.load(f)
            logger.info(f"Loaded {len(self.default_prompts)} default prompts")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in default prompts file: {e}")
            raise

        # 2. 사용자 프롬프트 로드 (선택적)
        self.user_prompts = {}
        if self.user_prompts_path.exists():
            try:
                with open(self.user_prompts_path, 'r', encoding='utf-8') as f:
                    self.user_prompts = json.load(f)
                logger.info(f"Loaded {len(self.user_prompts)} user prompts")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in user prompts file, ignoring: {e}")
            except Exception as e:
                logger.warning(f"Error loading user prompts, ignoring: {e}")

        # 3. 병합 (사용자 프롬프트가 우선)
        self._merge_prompts()

    def _merge_prompts(self) -> None:
        """기본 프롬프트와 사용자 프롬프트 병합 (사용자 우선)"""
        self.prompts = {}

        # 기본 프롬프트 복사
        for key, value in self.default_prompts.items():
            self.prompts[key] = value.copy()

        # 사용자 프롬프트로 덮어쓰기
        for key, value in self.user_prompts.items():
            self.prompts[key] = value.copy()

        logger.debug(f"Merged prompts: {len(self.prompts)} total")

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
        새 프롬프트 추가 (사용자 프롬프트로 저장)

        Args:
            prompt_key: 프롬프트 키
            name: 프롬프트 이름
            template: ChatML 템플릿
            temperature: temperature 값
        """
        new_prompt = {
            "name": name,
            "template": template,
            "temperature": temperature
        }
        self.user_prompts[prompt_key] = new_prompt
        self.prompts[prompt_key] = new_prompt.copy()
        logger.info(f"Added user prompt: {prompt_key}")

    def update_prompt(
        self,
        prompt_key: str,
        name: Optional[str] = None,
        template: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> None:
        """
        기존 프롬프트 업데이트 (사용자 프롬프트로 저장)

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

        # 사용자 프롬프트에 없으면 현재 값을 복사
        if prompt_key not in self.user_prompts:
            self.user_prompts[prompt_key] = self.prompts[prompt_key].copy()

        # 값 업데이트
        if name is not None:
            self.user_prompts[prompt_key]["name"] = name
            self.prompts[prompt_key]["name"] = name
        if template is not None:
            self.user_prompts[prompt_key]["template"] = template
            self.prompts[prompt_key]["template"] = template
        if temperature is not None:
            self.user_prompts[prompt_key]["temperature"] = temperature
            self.prompts[prompt_key]["temperature"] = temperature

        logger.info(f"Updated user prompt: {prompt_key}")

    def save(self) -> None:
        """
        사용자 프롬프트를 파일에 저장

        Raises:
            OSError: 파일 쓰기 실패 시
        """
        # 사용자 프롬프트가 없으면 저장하지 않음
        if not self.user_prompts:
            logger.debug("No user prompts to save")
            return

        # 디렉토리가 없으면 생성
        self.user_prompts_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.user_prompts_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_prompts, f, indent=2, ensure_ascii=False)
            logger.info(f"User prompts saved to {self.user_prompts_path}")
        except Exception as e:
            logger.error(f"Error saving user prompts: {e}")
            raise

    def reset_prompt(self, prompt_key: str) -> None:
        """
        프롬프트를 기본값으로 초기화

        Args:
            prompt_key: 프롬프트 키
        """
        if prompt_key in self.user_prompts:
            del self.user_prompts[prompt_key]
            logger.info(f"Reset prompt to default: {prompt_key}")

        # 기본 프롬프트로 복원
        if prompt_key in self.default_prompts:
            self.prompts[prompt_key] = self.default_prompts[prompt_key].copy()
        elif prompt_key in self.prompts:
            # 사용자가 추가한 프롬프트면 삭제
            del self.prompts[prompt_key]

    def is_user_modified(self, prompt_key: str) -> bool:
        """프롬프트가 사용자에 의해 수정되었는지 확인"""
        return prompt_key in self.user_prompts


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
    user_content = messages[0]['content'] if messages else ""
    print(f"   User message includes text: {text in user_content}")

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
