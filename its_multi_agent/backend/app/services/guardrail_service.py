"""
Guardrail 输入过滤服务。

使用 DFA 算法进行敏感词匹配。
通用敏感词命中 -> 拒绝
业务敏感词命中 -> 替换为 ***
"""
from dataclasses import dataclass
from typing import Optional

from utils.sensitive_word_loader import get_word_loader


@dataclass
class GuardrailCheckResult:
    """过滤检查结果。"""
    blocked: bool                    # 是否被拦截（通用敏感词）
    replaced: bool                   # 是否进行了替换（业务敏感词）
    filtered_text: Optional[str]     # 过滤后的文本（如果进行了替换）
    matched_common: list[str]        # 命中的通用敏感词
    matched_business: list[str]      # 命中的业务敏感词


class DFAFilter:
    """
    DFA（确定性有限自动机）敏感词过滤器。

    构建以敏感词为key的状态转移图，实现 O(1) 复杂度的字符串匹配。
    """

    def __init__(self, words: set[str]):
        """
        初始化 DFA 过滤器。

        Args:
            words: 敏感词集合
        """
        self._next: dict[tuple[int, str], int] = {}
        self._states: list[set[str]] = []
        self._build_trie(words)

    def _build_trie(self, words: set[str]) -> None:
        """构建状态转移图（字典树）。"""
        self._next = {}
        self._states = [set()]

        for word in words:
            if not word:
                continue
            self._add_word(word)

    def _add_word(self, word: str) -> None:
        """添加单个敏感词到 DFA。"""
        chars = list(word)
        state = 0

        for char in chars:
            key = (state, char)
            if key not in self._next:
                self._next[key] = len(self._states)
                self._states.append(set())
            state = self._next[key]
        self._states[state].add("")  # 标记为终态

    def filter_text(self, text: str, replace_char: str = "*") -> tuple[str, list[str]]:
        """
        过滤文本中的敏感词。

        Args:
            text: 原始文本
            replace_char: 替换字符

        Returns:
            (过滤后的文本, 命中的敏感词列表)
        """
        if not text:
            return "", []

        result = list(text)
        matched_words: list[str] = []
        chars = list(text)

        i = 0
        while i < len(chars):
            state = 0
            match_end = -1
            matched_word = ""

            for j in range(i, len(chars)):
                char = chars[j]
                key = (state, char)

                if key not in self._next:
                    break

                state = self._next[key]

                # 检查是否为终态（匹配结束）
                if "" in self._states[state]:
                    match_end = j
                    matched_word = text[i:j + 1]

            if match_end >= 0:
                matched_words.append(matched_word)
                for k in range(i, match_end + 1):
                    result[k] = replace_char
                i = match_end + 1
            else:
                i += 1

        return "".join(result), matched_words


class GuardrailService:
    """Guardrail 过滤服务。"""

    def __init__(self):
        self._word_loader = get_word_loader()
        self._common_filter: "DFAFilter | None" = None
        self._business_filter: "DFAFilter | None" = None
        self._build_filters()

    def _build_filters(self) -> None:
        """根据加载的词库构建 DFA 过滤器。"""
        common_words = self._word_loader.get_common_words()
        business_words = self._word_loader.get_business_words()

        self._common_filter = DFAFilter(common_words)
        self._business_filter = DFAFilter(business_words)

    def check_input(self, text: str) -> GuardrailCheckResult:
        """
        检查输入文本。

        Args:
            text: 用户输入文本

        Returns:
            GuardrailCheckResult: 包含 blocked, replaced, filtered_text, matched_* 等字段
        """
        if not text:
            return GuardrailCheckResult(
                blocked=False,
                replaced=False,
                filtered_text=text,
                matched_common=[],
                matched_business=[]
            )

        # 检查文件变化，必要时热更新
        self._word_loader.check_and_reload()

        # 第1步：检查通用敏感词（拒绝）
        filtered_common, matched_common = self._common_filter.filter_text(text)

        if matched_common:
            return GuardrailCheckResult(
                blocked=True,
                replaced=False,
                filtered_text=text,
                matched_common=matched_common,
                matched_business=[]
            )

        # 第2步：检查业务敏感词（替换）
        filtered_text, matched_business = self._business_filter.filter_text(text)

        return GuardrailCheckResult(
            blocked=False,
            replaced=len(matched_business) > 0,
            filtered_text=filtered_text,
            matched_common=[],
            matched_business=matched_business
        )


# 全局单例
guardrail_service = GuardrailService()
