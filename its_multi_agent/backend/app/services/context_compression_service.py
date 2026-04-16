"""
上下文压缩服务

当对话历史过长时，触发压缩逻辑：
1. 调用 LLM 从历史消息中提取结构化摘要
2. 清空 messages，保留 summary 到 SessionMemoryState

这样可以：
- 控制每次传给 Agent 的上下文长度
- 保留关键信息不被遗忘
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.ai.openai_client import sub_model
from infrastructure.logging.logger import logger
from schemas.session_memory import ConversationSummary, SessionMemoryState


# ========== 压缩触发阈值 ==========

# 消息数量阈值，超过则触发压缩
MESSAGE_COUNT_THRESHOLD = 10


# ========== LLM 摘要提取提示词 ==========

SUMMARY_EXTRACTION_PROMPT = """你是一个对话记忆提取助手。请从以下对话历史中提取关键信息，生成结构化摘要。

【输出格式】
请严格按照以下JSON格式返回，不要添加任何额外解释，不要使用markdown：
{{
    "summary_text": "对话的高层摘要，1-2句话概括本轮对话的核心内容",
    "entities": ["实体1", "实体2", ...],
    "preferences": ["偏好1", "偏好2", ...],
    "facts": ["事实1", "事实2", ...],
    "ongoing_issues": ["进行中的问题1", "进行中的问题2", ...],
    "resolved_issues": ["已解决的问题1", "已解决的问题2", ...],
    "decisions": ["决策1", "决策2", ...]
}}

【字段说明】
- summary_text: 一段简洁的摘要文字
- entities: 设备型号、品牌、地点、人名等实体（每个2-10个字）
- preferences: 用户的喜好和厌恶（如：喜欢华为、讨厌弹窗）
- facts: 用户提供的客观信息（如：住在昌平区、笔记本是ThinkPad T480）
- ongoing_issues: 当前还未解决的问题（如：电脑蓝屏、空调不制冷）
- resolved_issues: 本轮对话中已解决的问题（如：成功重装了系统）
- decisions: 对话中做出的重要决定（如：决定去4S店维修、选择方案B）

【要求】
- 所有字段都要返回，即使某一项为空也要返回空数组 []
- 不要编造信息，只提取对话中明确提到的内容
- 每个数组最多5个元素

【对话历史】
{_messages_text_}

【输出】"""


class ContextCompressionService:
    """
    上下文压缩服务

    负责检测是否需要压缩，以及执行压缩逻辑：
    1. 判断是否超过消息阈值
    2. 调用 LLM 提取结构化摘要
    3. 返回压缩后的状态
    """

    def __init__(self):
        # 阈值配置
        self._message_threshold = MESSAGE_COUNT_THRESHOLD
        # 用于提取摘要的模型
        self._extraction_model = sub_model

    async def compress_state_if_needed(
        self,
        state: SessionMemoryState,
        pending_user_input: str = "",
    ) -> Tuple[SessionMemoryState, bool, bool]:
        """
        检查并执行上下文压缩

        Args:
            state: 当前的会话状态
            pending_user_input: 待处理的最新用户输入（可能需要纳入摘要）

        Returns:
            (压缩后的状态, 是否触发了压缩, 是否需要持久化)
        """
        message_count = len(state.messages)

        # 判断是否需要压缩
        if message_count < self._message_threshold:
            # 不需要压缩，直接返回原状态
            return state, False, False

        logger.info(
            "[ContextCompression] triggered: message_count=%d threshold=%d",
            message_count,
            self._message_threshold,
        )

        # 执行压缩（异步 LLM 调用）
        compressed_state = await self._compress(state, pending_user_input)
        return compressed_state, True, True

    async def _compress(
        self,
        state: SessionMemoryState,
        pending_user_input: str,
    ) -> SessionMemoryState:
        """
        执行实际的压缩逻辑

        1. 拼接对话历史文本
        2. 调用 LLM 提取结构化信息
        3. 构建新的 SessionMemoryState
        """
        # 准备待分析的文本
        messages_text = self._prepare_messages_text(state, pending_user_input)

        # 调用 LLM 提取结构化摘要
        llm_result = await self._extract_with_llm(messages_text)

        # 保留原文片段用于追溯
        source_snippets = self._extract_key_snippets(state.messages)

        # 构建新的摘要
        new_summary = ConversationSummary(
            summary_text=llm_result.get("summary_text", ""),
            entities=llm_result.get("entities", []),
            preferences=llm_result.get("preferences", []),
            facts=llm_result.get("facts", []),
            ongoing_issues=llm_result.get("ongoing_issues", []),
            resolved_issues=llm_result.get("resolved_issues", []),
            decisions=llm_result.get("decisions", []),
            source_snippets=source_snippets,
        )

        # 构建压缩后的状态
        compressed_state = SessionMemoryState(
            system_messages=state.system_messages,
            messages=[],  # 清空消息，依赖摘要
            summary=new_summary,
            summary_version=state.summary_version + 1,
        )

        logger.info(
            "[ContextCompression] compressed: version=%d summary_text=%s entities=%d ongoing_issues=%d",
            compressed_state.summary_version,
            new_summary.summary_text[:50] if new_summary.summary_text else "",
            len(new_summary.entities),
            len(new_summary.ongoing_issues),
        )

        return compressed_state

    def _prepare_messages_text(
        self,
        state: SessionMemoryState,
        pending_input: str,
    ) -> str:
        """将对话历史拼接成纯文本，供 LLM 分析"""
        lines = []

        # 添加历史消息
        for msg in state.messages:
            if isinstance(msg, dict) and msg.get("content"):
                role = msg.get("role", "unknown")
                content = msg["content"]
                lines.append(f"{role}: {content}")

        # 添加待处理的输入（如果有）
        if pending_input:
            lines.append(f"user: {pending_input}")

        return "\n".join(lines)

    async def _extract_with_llm(self, messages_text: str) -> Dict[str, Any]:
        """
        调用 LLM 从对话历史中提取结构化信息

        Returns:
            包含 summary_text, entities, preferences, facts, ongoing_issues,
            resolved_issues, decisions 的字典
        """
        from config.settings import settings
        from infrastructure.ai.openai_client import sub_model_client

        # 构建 prompt
        prompt = SUMMARY_EXTRACTION_PROMPT.format(_messages_text_=messages_text)

        try:
            # 直接调用 LLM（使用 sub_model_client）
            client = sub_model_client
            response = await client.chat.completions.create(
                model=settings.SUB_MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.1,  # 低温度保证稳定性
                max_tokens=1000,
            )

            raw_output = response.choices[0].message.content.strip()
            logger.debug("[ContextCompression] LLM raw output: %s", raw_output[:500])

            # 解析 JSON 输出
            return self._parse_llm_output(raw_output)

        except Exception as e:
            logger.error("[ContextCompression] LLM extraction failed: %s", str(e))
            # 失败时返回空结果，不阻断主流程
            return {
                "summary_text": "对话摘要生成失败",
                "entities": [],
                "preferences": [],
                "facts": [],
                "ongoing_issues": [],
                "resolved_issues": [],
                "decisions": [],
            }

    def _parse_llm_output(self, raw_output: str) -> Dict[str, Any]:
        """
        解析 LLM 返回的 JSON 文本

        处理可能的 markdown 包装和多行 JSON 格式
        """
        # 去掉可能的 markdown 代码块标记
        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            # 尝试直接解析
            result = json.loads(cleaned)

            # 验证并规范化每个字段
            return {
                "summary_text": str(result.get("summary_text", ""))[:200],
                "entities": self._to_str_list(result.get("entities", [])),
                "preferences": self._to_str_list(result.get("preferences", [])),
                "facts": self._to_str_list(result.get("facts", [])),
                "ongoing_issues": self._to_str_list(result.get("ongoing_issues", [])),
                "resolved_issues": self._to_str_list(result.get("resolved_issues", [])),
                "decisions": self._to_str_list(result.get("decisions", [])),
            }
        except json.JSONDecodeError as e:
            logger.warning("[ContextCompression] JSON parse failed: %s, raw: %s", e, cleaned[:200])
            # 尝试从文本中提取信息作为兜底
            return self._fallback_parse(cleaned)

    def _to_str_list(self, value: Any) -> List[str]:
        """确保字段是字符串列表，最多5个元素"""
        if not isinstance(value, list):
            return []
        return [str(item)[:50] for item in value if item][:5]

    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        """
        JSON 解析失败时的兜底逻辑

        简单尝试提取关键段落
        """
        result = {
            "summary_text": text[:100] if text else "解析失败",
            "entities": [],
            "preferences": [],
            "facts": [],
            "ongoing_issues": [],
            "resolved_issues": [],
            "decisions": [],
        }

        # 尝试找 summary_text
        import re
        summary_match = re.search(r'summary_text["\s:]+([^"]+)', text)
        if summary_match:
            result["summary_text"] = summary_match.group(1).strip()[:100]

        return result

    def _extract_key_snippets(self, messages: List[Dict[str, Any]]) -> List[str]:
        """提取关键消息片段（用于追溯）"""
        snippets = []

        # 保留最近3条消息的原文片段
        for msg in messages[-3:]:
            if isinstance(msg, dict) and msg.get("content"):
                content = msg["content"]
                # 截取前100字符
                if len(content) > 100:
                    content = content[:100] + "..."
                snippets.append(content)

        return snippets

    def format_summary_message(self, summary: ConversationSummary) -> Dict[str, str]:
        """
        将结构化摘要格式化为一条消息，用于注入到 Agent 上下文

        Returns:
            一条 role=system 的消息，包含摘要的文本描述
        """
        parts = ["【会话记忆摘要】"]

        if summary.summary_text:
            parts.append(f"概述：{summary.summary_text}")

        if summary.entities:
            parts.append(f"已知实体：{', '.join(summary.entities)}")

        if summary.preferences:
            parts.append(f"用户偏好：{', '.join(summary.preferences)}")

        if summary.facts:
            parts.append(f"已知事实：{', '.join(summary.facts)}")

        if summary.ongoing_issues:
            parts.append(f"进行中的问题：{', '.join(summary.ongoing_issues)}")

        if summary.resolved_issues:
            parts.append(f"已解决问题：{', '.join(summary.resolved_issues)}")

        if summary.decisions:
            parts.append(f"已做决策：{', '.join(summary.decisions)}")

        content = "\n".join(parts)

        return {"role": "system", "content": content}


# 全局单例
context_compression_service = ContextCompressionService()
