"""
会话记忆状态数据模型

定义会话记忆的结构化存储格式，支持：
- 短期记忆：原始消息列表
- 长期记忆：结构化摘要（实体、偏好、事实、待办）
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    """
    结构化对话摘要

    从历史对话中提取的关键信息，用于长期记忆保留。
    即使清空了原始消息，这些结构化信息依然可以被利用。
    """

    # 文本摘要 - 对整段对话的高度概括
    summary_text: str = Field(
        default="",
        description="对话的高层摘要，简要描述本轮对话的核心内容"
    )

    # 提及的实体 - 设备、品牌、型号、地点等
    entities: List[str] = Field(
        default_factory=list,
        description="对话中提到的关键实体（如设备型号、品牌、地点、车型等）"
    )

    # 用户偏好 - 喜欢/不喜欢的事物
    preferences: List[str] = Field(
        default_factory=list,
        description="用户的偏好和 dislikes（如：喜欢华为、讨厌频繁弹窗）"
    )

    # 事实性信息 - 用户提供的客观信息
    facts: List[str] = Field(
        default_factory=list,
        description="用户分享的事实性信息（如：我的笔记本是ThinkPad、住在昌平）"
    )

    # 进行中的问题/任务 - 需要后续跟进的事项
    ongoing_issues: List[str] = Field(
        default_factory=list,
        description="用户当前正在处理的问题或任务（如：电脑蓝屏、空调不制冷）"
    )

    # 已完成的问题 - 已解决的事项
    resolved_issues: List[str] = Field(
        default_factory=list,
        description="本轮对话中已解决的问题（如：成功重装了系统）"
    )

    # 关键决策 - 对话中做出的重要决定
    decisions: List[str] = Field(
        default_factory=list,
        description="对话中产生的关键决策（如：决定去4S店维修、选择了方案B）"
    )

    # 结构化信息的原始文本来源（便于追溯）
    source_snippets: List[str] = Field(
        default_factory=list,
        description="用于提取结构化信息的原始消息片段"
    )


class SessionMemoryState(BaseModel):
    """
    会话记忆状态

    包含了一个会话的全部记忆：
    - system_messages: 系统级指令（不变）
    - messages: 对话消息（短期记忆，可能被压缩）
    - summary: 结构化摘要（长期记忆，压缩后保留）
    - summary_version: 摘要版本号
    """

    # 系统消息列表
    system_messages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="系统指令消息"
    )

    # 对话消息列表（短期记忆）
    messages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="用户与助手的对话记录"
    )

    # 结构化摘要（长期记忆）
    summary: Optional[ConversationSummary] = Field(
        default=None,
        description="从历史对话中提取的结构化摘要"
    )

    # 摘要版本号，每次压缩后递增
    summary_version: int = Field(
        default=1,
        description="摘要版本号"
    )

    class Config:
        # 允许任意类型字段
        extra = "allow"
