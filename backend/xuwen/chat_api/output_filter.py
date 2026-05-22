"""Assistant 输出过滤。

历史聊天里的 `[图片]` / `[[表情]]` 只是导入占位符，模型不能真的发送这些内容。
这里在 LLM 输出层做最后一道防线；真正可渲染的表情包使用 `[sticker:名字]`，不受影响。
"""

from __future__ import annotations

import re

_MEDIA_PLACEHOLDER_RE = re.compile(
    r"\[(?:图片|语音|视频|文件|表情|动画表情|撤回|系统消息)(?:[:：][^\]]*)?\]\s*[:：]?\s*"
)
_QQ_FACE_RE = re.compile(r"\[\[[^\]]+\]\]\s*[:：]?\s*")
_REPLY_MEDIA_RE = re.compile(
    r"\[回复[^\n\]]*(?:图片|语音|视频|文件|表情|动画表情)[^\n\]]*\]\s*[:：]?\s*"
)
_TRAILING_PARTIAL_STICKER_RE = re.compile(r"\s*\[sticker(?::|=)[^\]\s]*$")
_LEADING_PUNCT_RE = re.compile(r"^[\s,，.。:：;；、~～]+")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_STREAM_TAIL_CHARS = 16


def sanitize_assistant_text(text: str, *, fallback_empty: bool = True) -> str:
    """移除模型复制出来的历史占位符。

    保留 `[sticker:xxx]`，因为它是当前系统真实支持的输出协议。
    """
    if not text:
        return text

    out = _REPLY_MEDIA_RE.sub("", text)
    out = _MEDIA_PLACEHOLDER_RE.sub("", out)
    out = _QQ_FACE_RE.sub("", out)
    out = _TRAILING_PARTIAL_STICKER_RE.sub("", out)
    out = _MULTI_SPACE_RE.sub(" ", out)
    if fallback_empty:
        out = "\n".join(_LEADING_PUNCT_RE.sub("", line).rstrip() for line in out.splitlines())
        out = out.strip()
    else:
        out = "\n".join(_LEADING_PUNCT_RE.sub("", line) for line in out.splitlines())
    if fallback_empty and text.strip() and not out:
        return "嗯"
    return out


class AssistantOutputFilter:
    """流式输出过滤器。

    为避免把拆开的 `[图片]` 半截先发给前端，保留一小段尾巴，等下个 chunk
    到来后再统一过滤。最终 flush 时会处理剩余内容。
    """

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, piece: str) -> str:
        if not piece:
            return ""
        self._buffer += piece
        if len(self._buffer) <= _STREAM_TAIL_CHARS:
            return ""

        cut = len(self._buffer) - _STREAM_TAIL_CHARS
        # 不要在 bracket token 中间切开，尤其是较长的 [sticker:xxx]。
        last_bracket = self._buffer.rfind("[", 0, cut)
        if last_bracket >= 0:
            close_bracket = self._buffer.find("]", last_bracket)
            if close_bracket == -1 or close_bracket >= cut:
                cut = last_bracket
        if last_bracket >= 0 and cut - last_bracket < _STREAM_TAIL_CHARS:
            cut = last_bracket
        if cut <= 0:
            return ""

        raw = self._buffer[:cut]
        self._buffer = self._buffer[cut:]
        return sanitize_assistant_text(raw, fallback_empty=False)

    def flush(self) -> str:
        raw = self._buffer
        self._buffer = ""
        return sanitize_assistant_text(raw, fallback_empty=False)
