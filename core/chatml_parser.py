"""
ChatML 파서 및 프롬프트 변수 치환

ChatML 형식 (<|im_start|>role...content...<|im_end|>)을 OpenAI messages 형식으로 변환하고,
{{text}}, {{instruction}} 등의 변수를 동적으로 치환합니다.
"""

import re
import logging
from typing import List, Dict, Any


logger = logging.getLogger(__name__)


class ChatMLParser:
    """ChatML 형식 파서"""

    # ChatML 역할 패턴: <|im_start|>role\ncontent (다음 <|im_start|> 또는 <|im_end|> 또는 문자열 끝까지)
    ROLE_PATTERN = re.compile(
        r'<\|im_start\|>(\w+)\n(.*?)(?=<\|im_start\|>|<\|im_end\|>|$)',
        re.DOTALL  # . matches newlines
    )

    # 변수 패턴: {{variable_name}}
    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    @staticmethod
    def is_chatml(template: str) -> bool:
        """
        문자열이 ChatML 형식인지 확인

        Args:
            template: 확인할 템플릿 문자열

        Returns:
            ChatML 형식이면 True

        Example:
            >>> ChatMLParser.is_chatml("<|im_start|>system\\nYou are helpful<|im_end|>")
            True
            >>> ChatMLParser.is_chatml("Regular text")
            False
        """
        return '<|im_start|>' in template

    @staticmethod
    def parse(template: str) -> List[Dict[str, str]]:
        """
        ChatML 템플릿을 OpenAI messages 형식으로 변환

        Args:
            template: ChatML 형식 템플릿

        Returns:
            OpenAI messages 형식의 리스트
            [{"role": "system", "content": "..."},
             {"role": "user", "content": "..."}]

        Raises:
            ValueError: 유효한 ChatML 형식이 아닌 경우

        Example:
            >>> template = '''<|im_start|>system
            ... You are a helpful assistant.
            ... <|im_end|>
            ... <|im_start|>user
            ... Hello!
            ... <|im_end|>'''
            >>> ChatMLParser.parse(template)
            [{'role': 'system', 'content': 'You are a helpful assistant.'},
             {'role': 'user', 'content': 'Hello!'}]
        """
        matches = ChatMLParser.ROLE_PATTERN.findall(template)

        if not matches:
            logger.warning("No valid ChatML blocks found in template")
            raise ValueError("No valid ChatML blocks found in template")

        messages = []
        for role, content in matches:
            messages.append({
                "role": role.strip(),
                "content": content.strip()
            })

        logger.debug(f"Parsed {len(messages)} ChatML messages")
        return messages

    @staticmethod
    def substitute_variables(template: str, variables: Dict[str, str]) -> str:
        """
        템플릿의 변수를 실제 값으로 치환

        Args:
            template: 변수가 포함된 템플릿 문자열
            variables: 변수명-값 딕셔너리

        Returns:
            변수가 치환된 문자열

        Example:
            >>> template = "User said: {{text}}. Instruction: {{instruction}}"
            >>> variables = {"text": "Hello", "instruction": "Translate to French"}
            >>> ChatMLParser.substitute_variables(template, variables)
            'User said: Hello. Instruction: Translate to French'
        """
        result = template
        substitution_count = 0

        for key, value in variables.items():
            pattern = f'{{{{{key}}}}}'
            if pattern in result:
                result = result.replace(pattern, value)
                substitution_count += 1
                logger.debug(f"Substituted variable: {key}")

        if substitution_count > 0:
            logger.debug(f"Total {substitution_count} variables substituted")

        return result

    @staticmethod
    def parse_and_substitute(
        template: str,
        variables: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """
        변수 치환 + ChatML 파싱을 한 번에 수행

        Args:
            template: ChatML 형식 템플릿 (변수 포함 가능)
            variables: 변수명-값 딕셔너리

        Returns:
            OpenAI messages 형식의 리스트

        Example:
            >>> template = '''<|im_start|>system
            ... You are a translator.
            ... <|im_end|>
            ... <|im_start|>user
            ... Translate: {{text}}
            ... <|im_end|>'''
            >>> variables = {"text": "Hello world"}
            >>> ChatMLParser.parse_and_substitute(template, variables)
            [{'role': 'system', 'content': 'You are a translator.'},
             {'role': 'user', 'content': 'Translate: Hello world'}]
        """
        # 1. 변수 치환
        substituted = ChatMLParser.substitute_variables(template, variables)

        # 2. ChatML 파싱
        if ChatMLParser.is_chatml(substituted):
            return ChatMLParser.parse(substituted)
        else:
            # ChatML 형식이 아니면 user 메시지로 처리
            logger.debug("Not ChatML format, treating as user message")
            return [{"role": "user", "content": substituted}]

    @staticmethod
    def get_variables_in_template(template: str) -> List[str]:
        """
        템플릿에 포함된 변수 이름 목록 추출

        Args:
            template: 템플릿 문자열

        Returns:
            변수 이름 리스트

        Example:
            >>> template = "{{text}} and {{instruction}} here"
            >>> ChatMLParser.get_variables_in_template(template)
            ['text', 'instruction']
        """
        matches = ChatMLParser.VARIABLE_PATTERN.findall(template)
        return list(set(matches))  # 중복 제거


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing ChatMLParser ===\n")

    # 테스트 1: ChatML 형식 확인
    print("1. Testing is_chatml()...")
    assert ChatMLParser.is_chatml("<|im_start|>system\nHello<|im_end|>") == True
    assert ChatMLParser.is_chatml("Regular text") == False
    print("   [OK] ChatML detection works")

    # 테스트 2: ChatML 파싱
    print("\n2. Testing parse()...")
    template = """<|im_start|>system
You are a helpful assistant.
<|im_end|>
<|im_start|>user
Hello, how are you?
<|im_end|>"""

    messages = ChatMLParser.parse(template)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    print("   [OK] ChatML parsing works")
    print(f"   Parsed: {messages}")

    # 테스트 3: 변수 치환
    print("\n3. Testing substitute_variables()...")
    template = "User: {{text}}\nInstruction: {{instruction}}"
    variables = {
        "text": "Hello world",
        "instruction": "Translate to Korean"
    }
    result = ChatMLParser.substitute_variables(template, variables)
    assert "Hello world" in result
    assert "Translate to Korean" in result
    print("   [OK] Variable substitution works")
    print(f"   Result: {result}")

    # 테스트 4: 통합 (변수 치환 + ChatML 파싱)
    print("\n4. Testing parse_and_substitute()...")
    template = """<|im_start|>system
You are a grammar correction assistant.
<|im_end|>
<|im_start|>user
Correct this text: {{text}}
<|im_end|>"""

    variables = {"text": "I are student"}
    messages = ChatMLParser.parse_and_substitute(template, variables)
    assert len(messages) == 2
    assert "I are student" in messages[1]["content"]
    print("   [OK] Integrated parsing works")
    print(f"   Messages: {messages}")

    # 테스트 5: 변수 추출
    print("\n5. Testing get_variables_in_template()...")
    template = "{{text}} and {{instruction}} and {{text}} again"
    vars_list = ChatMLParser.get_variables_in_template(template)
    assert set(vars_list) == {"text", "instruction"}
    print("   [OK] Variable extraction works")
    print(f"   Variables found: {vars_list}")

    print("\n[OK] All ChatML tests passed!")
