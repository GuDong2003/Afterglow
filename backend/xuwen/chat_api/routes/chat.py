"""/v1/chat/completions：OpenAI 兼容的对话端点。

工作流程：
    1. 读取请求中最后一条 user message（可能含图片）
    2. 把图片落盘（image_store），记录 SHA 列表用于回写
    3. 处理 multimodal：
        - 若 chat_model_supports_vision：原样转发图片给主 LLM
        - 否则：调 VisionClient 把图片转描述，注入到 text
    4. 用 HybridRetriever 召回相关历史（基于纯文本部分）
    5. 可选联网搜索 / URL 网页读取，注入外部上下文
    6. 用 Jinja2 模板渲染 system prompt
    7. 调用 LLMClient（流 / 非流）
    8. 完整 assistant 文本 + 用户图片 SHA → enqueue 到 writeback queue
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from xuwen.chat_api.companion_prompt import (
    build_persona_card_with_companion_context,
    empty_retrieval_result,
    render_life_memory_context,
)
from xuwen.chat_api.image_store import ImageError, save_data_url
from xuwen.chat_api.llm_client import GenerationParams
from xuwen.chat_api.output_filter import AssistantOutputFilter, sanitize_assistant_text
from xuwen.chat_api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ImagePart,
    ImageUrlPayload,
    TextPart,
    Usage,
)
from xuwen.chat_api.schemas import (
    ChatMessage as APIChatMessage,
)
from xuwen.chat_api.state import AppState, get_state
from xuwen.chat_api.vision_client import VisionClient
from xuwen.chat_api.web_fetch import render_url_context, resolve_fetch_urls
from xuwen.chat_api.web_search import render_web_context, should_search_web
from xuwen.core.errors import RetrievalError, XuwenError
from xuwen.core.models import RetrievalQuery
from xuwen.memory.writer import WritebackTurn
from xuwen.persona.prompt import ChatMessage as PromptMessage
from xuwen.persona.prompt import build_chat_messages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    req: ChatCompletionRequest,
    request: Request,
    state: AppState = Depends(get_state),
) -> StreamingResponse | ChatCompletionResponse:
    trace_id = str(getattr(request.state, "request_id", "") or "")
    # 找最后一条 user message 作为当前问题
    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="messages 中至少要有一条 role=user")
    last_user = user_messages[-1]

    # 1) 处理图片：落盘 + 收集 SHA + 根据配置决定是否调 VLM
    image_shas: list[str] = []
    vlm_descriptions: list[str] = []
    images_in_last = last_user.image_urls()

    if images_in_last:
        if not state.settings.vision_enabled:
            raise HTTPException(
                status_code=400,
                detail="未启用视觉理解。请在后端 .env 设置 VISION_ENABLED=true。",
            )

        # 落盘原图
        for url in images_in_last:
            try:
                ref = save_data_url(url, state.settings)
            except ImageError as e:
                raise HTTPException(status_code=400, detail=e.message) from e
            image_shas.append(ref.sha)

        # 若主模型不支持视觉，调 VLM 把图片转描述
        if not state.settings.chat_model_supports_vision:
            if not state.settings.vision_api_url or not state.settings.vision_api_key.get_secret_value():
                raise HTTPException(
                    status_code=400,
                    detail="主模型不支持视觉，且 VISION_API_URL / VISION_API_KEY 未配置。"
                    "请在 .env 配置 VLM 或改用支持视觉的主模型。",
                )
            async with VisionClient(state.settings) as vc:
                vlm_descriptions = await vc.describe_images(images_in_last)

    # 2) 准备发送给 LLM 的 messages（不含我们自己生成的 system，那由 prompt builder 加）
    # 历史消息：剔除最后一条 user，保留其它 user/assistant；统一展平为纯文本，
    # 因为历史里出现的多模态 LLM 也未必能消化二次。
    recent: list[PromptMessage] = [
        PromptMessage(role=m.role, content=m.text_only())
        for m in req.messages[:-1]
        if m.role in {"user", "assistant"}
    ]

    # 3) 构造当前 user 文本（用于检索 + prompt）
    current_user_text = last_user.text_only().strip()
    if vlm_descriptions:
        # 把 VLM 描述附加到用户消息里，下游模型才能"看到"
        desc_block = "\n".join(
            f"[图片{i + 1}描述：{d}]" for i, d in enumerate(vlm_descriptions)
        )
        current_user_text = (current_user_text + "\n" + desc_block).strip()

    # 4) 检索（基于文本 query）+ 记录延迟
    retrieval_query = current_user_text if current_user_text else "（用户发了一张图片）"
    _retrieval_start = time.perf_counter()
    try:
        retrieved = await state.retriever.retrieve(
            RetrievalQuery(
                query_text=retrieval_query,
                conversation_id=req.conversation_id,
            )
        )
        state.metrics.record(
            "retrieval",
            (time.perf_counter() - _retrieval_start) * 1000,
            detail=f"final={len(retrieved.fused)}",
        )
    except RetrievalError as e:
        logger.warning("检索失败，降级到无 RAG 模式：%s", e.message)
        state.metrics.record(
            "retrieval",
            (time.perf_counter() - _retrieval_start) * 1000,
            error=type(e).__name__,
        )
        retrieved = empty_retrieval_result()

    model_name = req.model or state.settings.chat_model

    # 5) 注入新关系记忆和 AI 当天生活状态。这层优先级高于历史 RAG。
    relationship_block = await state.relationship_memory.render_context(retrieval_query)
    life = await state.life.decide_for_turn(
        llm=state.life_llm,
        model=state.settings.resolved_life_model,
        current_user_text=current_user_text,
        recent=recent,
        relationship_context=relationship_block,
        memory_context=render_life_memory_context(retrieved, state.settings),
        trigger="chat",
        trace_id=trace_id,
        metrics=state.metrics,
    )
    persona_card = build_persona_card_with_companion_context(
        settings=state.settings,
        life=life,
        relationship_context=relationship_block,
        style_query=current_user_text,
    )
    web_context = ""
    web_should_search = should_search_web(current_user_text)
    if state.web_search is not None and web_should_search:
        web_results = await state.web_search.search(
            current_user_text,
            trace_id=trace_id,
            metrics=state.metrics,
        )
        web_context = render_web_context(web_results)
    else:
        _record_web_search_skipped(
            state,
            trace_id=trace_id,
            query=current_user_text,
            should_search=web_should_search,
        )

    url_context = ""
    urls: list[str] = []
    if state.web_fetch is not None:
        urls = await resolve_fetch_urls(
            current_user_text,
            llm=state.life_llm,
            model=state.settings.resolved_life_model,
            limit=state.settings.web_fetch_max_urls,
            trace_id=trace_id,
            metrics=state.metrics,
        )
        if urls:
            url_results = await state.web_fetch.fetch_many(
                urls,
                trace_id=trace_id,
                metrics=state.metrics,
            )
            url_context = render_url_context(url_results)
    if not urls:
        _record_web_fetch_skipped(state, trace_id=trace_id, urls=urls)

    # 6) 构造 prompt messages
    messages = build_chat_messages(
        settings=state.settings,
        persona_card=persona_card,
        retrieved=retrieved,
        recent=recent,
        current_user_message=current_user_text or "（图片）",
        web_context=web_context,
        url_context=url_context,
    )

    # 6.1) 若主模型支持视觉，重写最后一条 user 为 multimodal 形式
    if (
        images_in_last
        and state.settings.chat_model_supports_vision
        and messages
        and messages[-1]["role"] == "user"
    ):
        text_for_user = messages[-1]["content"]
        if isinstance(text_for_user, str):
            multimodal_content: list[dict[str, Any]] = [
                {"type": "text", "text": text_for_user},
            ]
            for url in images_in_last:
                multimodal_content.append(
                    {"type": "image_url", "image_url": {"url": url}}
                )
            messages[-1] = {"role": "user", "content": multimodal_content}  # type: ignore[dict-item]

    # 7) 生成参数
    params = GenerationParams(
        temperature=req.temperature,
        top_p=req.top_p,
        max_tokens=req.max_tokens,
        presence_penalty=req.presence_penalty,
        frequency_penalty=req.frequency_penalty,
    )

    # 8) 流式 or 非流
    if req.stream:
        return StreamingResponse(
            _stream_response(
                state=state,
                messages=messages,
                params=params,
                model_name=model_name,
                conversation_id=req.conversation_id,
                user_text=current_user_text,
                image_shas=image_shas,
                initial_delay_seconds=life.reply_delay_seconds,
                trace_id=trace_id,
            ),
            media_type="text/event-stream",
        )

    await _sleep_for_life_delay(life.reply_delay_seconds, state)
    _llm_start = time.perf_counter()
    try:
        assistant_text = sanitize_assistant_text(
            await state.llm.complete_chat(
                messages,
                params,
                model=model_name,
                trace_id=trace_id,
                stage="chat.complete",
                metrics=state.metrics,
            )
        )
        state.metrics.record(
            "llm.complete",
            (time.perf_counter() - _llm_start) * 1000,
            detail=model_name,
        )
    except XuwenError as e:
        state.metrics.record(
            "llm.complete",
            (time.perf_counter() - _llm_start) * 1000,
            error=e.code,
        )
        raise
    # 异步回写
    if req.conversation_id:
        await state.writeback.enqueue_turn(
            WritebackTurn(
                conversation_id=req.conversation_id,
                user_text=current_user_text,
                assistant_text=assistant_text,
                user_image_shas=image_shas,
            )
        )
        await state.relationship_memory.remember_turn(
            conversation_id=req.conversation_id,
            user_text=current_user_text,
            assistant_text=assistant_text,
        )
    return ChatCompletionResponse(
        model=model_name,
        choices=[
            Choice(
                index=0,
                message=APIChatMessage(role="assistant", content=assistant_text),
                finish_reason="stop",
            )
        ],
        usage=Usage(),
        trace_id=trace_id,
    )


async def _stream_response(
    *,
    state: AppState,
    messages: list[dict[str, Any]],
    params: GenerationParams,
    model_name: str,
    conversation_id: str | None,
    user_text: str,
    image_shas: list[str],
    initial_delay_seconds: int,
    trace_id: str,
) -> AsyncIterator[bytes]:
    """以 OpenAI SSE 格式生成 chunk。"""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    buffer: list[str] = []
    output_filter = AssistantOutputFilter()

    def _chunk_dict(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "trace_id": trace_id,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish,
                }
            ],
        }

    # 首块带 role
    yield _format_sse(_chunk_dict({"role": "assistant"}))
    await _sleep_for_life_delay(initial_delay_seconds, state)

    _stream_start = time.perf_counter()
    try:
        async for piece in state.llm.stream_chat(
            messages,
            params,
            model=model_name,
            trace_id=trace_id,
            stage="chat.stream",
            metrics=state.metrics,
        ):
            filtered = output_filter.feed(piece)
            if not filtered:
                continue
            buffer.append(filtered)
            yield _format_sse(_chunk_dict({"content": filtered}))
        tail = output_filter.flush()
        if tail:
            buffer.append(tail)
            yield _format_sse(_chunk_dict({"content": tail}))
        state.metrics.record(
            "llm.stream",
            (time.perf_counter() - _stream_start) * 1000,
            detail=f"{model_name},chars={sum(len(p) for p in buffer)}",
        )
    except XuwenError as e:
        state.metrics.record(
            "llm.stream",
            (time.perf_counter() - _stream_start) * 1000,
            error=e.code,
        )
        yield _format_sse(
            {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "trace_id": trace_id,
                }
            }
        )
        yield b"data: [DONE]\n\n"
        return

    yield _format_sse(_chunk_dict({}, finish="stop"))
    yield b"data: [DONE]\n\n"

    # 流结束后回写完整 assistant 文本（+ 用户图片 SHA）
    assistant_text = "".join(buffer)
    if conversation_id and assistant_text:
        await state.writeback.enqueue_turn(
            WritebackTurn(
                conversation_id=conversation_id,
                user_text=user_text,
                assistant_text=assistant_text,
                user_image_shas=image_shas,
            )
        )
        await state.relationship_memory.remember_turn(
            conversation_id=conversation_id,
            user_text=user_text,
            assistant_text=assistant_text,
        )


def _format_sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _record_web_search_skipped(
    state: AppState,
    *,
    trace_id: str,
    query: str,
    should_search: bool,
) -> None:
    if not state.settings.web_access_enabled:
        reason = "web_access_disabled"
    elif state.web_search is None:
        reason = "web_search_client_inactive"
    elif not should_search:
        reason = "trigger_not_matched"
    else:
        reason = "unknown"
    state.metrics.record(
        "web.search.skipped",
        0.0,
        detail=(
            f"reason={reason},trace={trace_id},"
            f"should_search={str(should_search).lower()},query_chars={len(query)}"
        ),
    )


def _record_web_fetch_skipped(
    state: AppState,
    *,
    trace_id: str,
    urls: list[str],
) -> None:
    if not state.settings.web_access_enabled:
        reason = "web_access_disabled"
    elif not state.settings.web_fetch_enabled:
        reason = "web_fetch_disabled"
    elif state.web_fetch is None:
        reason = "web_fetch_client_inactive"
    elif not urls:
        reason = "no_url"
    else:
        reason = "unknown"
    state.metrics.record(
        "web.fetch.skipped",
        0.0,
        detail=f"reason={reason},trace={trace_id},url_count={len(urls)}",
    )


async def _sleep_for_life_delay(seconds: int, state: AppState) -> None:
    bounded = max(0, min(seconds, state.settings.life_max_reply_delay_seconds))
    if bounded:
        await asyncio.sleep(bounded)


# 为了避免 mypy 报 unused-imports 而保留导入
_unused: tuple[type, ...] = (ChatMessage, ImagePart, ImageUrlPayload, TextPart)
