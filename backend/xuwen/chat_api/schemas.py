"""OpenAI 兼容的 pydantic 模型 + 内部辅助 schema。

只覆盖 chat/completions 子集与 memory 控制接口；不实现 functions / tools 等本期用不到的字段。
多模态：ChatMessage.content 同时接受 string 与 list[ContentPart]（OpenAI 多模态标准）。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["system", "user", "assistant"]


# ---------------------------------------------------------------------------
# OpenAI 多模态 content
# ---------------------------------------------------------------------------


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageUrlPayload(BaseModel):
    url: str
    # 兼容 OpenAI 的 detail 字段（low / high / auto），本期不强依赖
    detail: str | None = None


class ImagePart(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageUrlPayload


# ContentPart 联合类型
ContentPart = TextPart | ImagePart


# ---------------------------------------------------------------------------
# OpenAI 兼容 chat
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Role
    # OpenAI 多模态规范：content 可以是 str 或 list[ContentPart]
    content: str | list[ContentPart]

    def text_only(self) -> str:
        """提取纯文本，丢弃图片部分（用于无视觉模型 fallback）。"""
        if isinstance(self.content, str):
            return self.content
        return "".join(p.text for p in self.content if isinstance(p, TextPart))

    def image_urls(self) -> list[str]:
        """提取所有 image_url。"""
        if isinstance(self.content, str):
            return []
        return [p.image_url.url for p in self.content if isinstance(p, ImagePart)]

    def has_images(self) -> bool:
        if isinstance(self.content, str):
            return False
        return any(isinstance(p, ImagePart) for p in self.content)


class ChatCompletionRequest(BaseModel):
    """OpenAI 兼容的 chat/completions 请求。"""

    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    # 非 OpenAI 字段，用来关联回写
    conversation_id: str | None = Field(
        default=None,
        description="会话标识，用于把这一轮回写到 live_messages 表。",
    )

    @field_validator("messages")
    @classmethod
    def _at_least_one_user(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v:
            raise ValueError("messages 不能为空")
        if not any(m.role == "user" for m in v):
            raise ValueError("messages 中至少要有一条 role=user")
        return v


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)
    trace_id: str = ""


# ---------------------------------------------------------------------------
# memory 控制接口
# ---------------------------------------------------------------------------


class MemoryStatsResponse(BaseModel):
    friend_messages: int
    dialogue_windows: int
    response_pairs: int = 0
    live_messages: int
    relationship_memories: int = 0
    writeback_enabled: bool
    writeback_paused: bool


class MemorySearchRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    top_k: int = 12


class MemorySearchHit(BaseModel):
    chunk_id: str
    kind: Literal["friend", "window", "live", "response_pair"]
    text: str
    score: float
    rank: int
    timestamp_ms: int
    session_id: str = ""
    sender_name: str = ""
    source: Literal["history", "live"] = "history"
    warmth: float = 0.0


class MemorySearchResponse(BaseModel):
    fused: list[MemorySearchHit]
    response_pairs: list[MemorySearchHit] = []
    friend_examples: list[MemorySearchHit]
    dialogue_windows: list[MemorySearchHit]
    recent_live: list[MemorySearchHit] = []
    trace_id: str = ""


class AppInfoResponse(BaseModel):
    """`/info` 端点返回应用元数据，供前端读 APP_NAME / slogan。"""

    app_name: str
    app_slogan: str
    friend_name: str
    self_name: str
    relationship_type: str
    relationship_description: str
    persona_template: str
    embedding_model: str
    chat_model: str
    version: str
    has_persona_card: bool


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    ready: bool
    issues: list[str] = []


# ---------------------------------------------------------------------------
# 错误
# ---------------------------------------------------------------------------


class ErrorPayload(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def to_search_hit(chunk: Any) -> MemorySearchHit:
    return MemorySearchHit(
        chunk_id=chunk.chunk_id,
        kind=chunk.kind,
        text=chunk.text,
        score=float(chunk.score),
        rank=int(chunk.rank),
        timestamp_ms=int(chunk.timestamp_ms),
        session_id=chunk.session_id,
        sender_name=chunk.sender_name,
        source=chunk.source,
        warmth=float(chunk.warmth),
    )
