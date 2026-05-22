"""轻量运行时指标收集。

环形缓冲（最近 N 次）记录：
- LLM 调用：model / status / latency_ms / token / request_id / error
- Embedding 调用：batch_size / latency_ms / status / error
- Retrieval：query_len / friend_top / window_top / final_k / latency_ms

线程不安全但够用——FastAPI worker 一般单 event loop，调用都在主协程；
即使有并发也只是计数轻微偏差，无关紧要。
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CallRecord:
    """一次外部调用的元数据。敏感字段（如 prompt 正文 / API key）一律不存。"""

    ts_ms: int
    latency_ms: float
    status: str          # ok / error
    detail: str = ""     # 简短描述（错误类型 / HTTP 状态码 / 模型名）


@dataclass(slots=True)
class ModelCallRecord:
    """一次上游模型请求的可诊断链路记录。不保存 API key。"""

    ts_ms: int
    trace_id: str
    stage: str
    attempt: int
    model: str
    url: str
    stream: bool
    latency_ms: float
    status: str
    status_code: int | None = None
    upstream_request_id: str = ""
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(slots=True)
class MetricStats:
    """某类调用的聚合统计。"""

    count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    last_records: list[CallRecord] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.count if self.count else 0.0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.count if self.count else 0.0


class MetricsRecorder:
    """全局指标收集器。"""

    def __init__(self, capacity: int = 100) -> None:
        self.capacity = capacity
        self._buffers: dict[str, deque[CallRecord]] = {}
        self._model_chain: deque[ModelCallRecord] = deque(maxlen=capacity)

    def record(self, kind: str, latency_ms: float, *, error: str | None = None, detail: str = "") -> None:
        buf = self._buffers.setdefault(kind, deque(maxlen=self.capacity))
        rec = CallRecord(
            ts_ms=int(time.time() * 1000),
            latency_ms=round(latency_ms, 2),
            status="error" if error else "ok",
            detail=error or detail,
        )
        buf.append(rec)

    def record_model_call(
        self,
        *,
        trace_id: str,
        stage: str,
        attempt: int,
        model: str,
        url: str,
        stream: bool,
        latency_ms: float,
        status: str,
        status_code: int | None = None,
        upstream_request_id: str = "",
        request: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        self._model_chain.append(
            ModelCallRecord(
                ts_ms=int(time.time() * 1000),
                trace_id=trace_id,
                stage=stage,
                attempt=attempt,
                model=model,
                url=url,
                stream=stream,
                latency_ms=round(latency_ms, 2),
                status=status,
                status_code=status_code,
                upstream_request_id=upstream_request_id,
                request=request or {},
                response=response or {},
                error=error,
            )
        )

    def model_chain(self, trace_id: str | None = None, limit: int = 50) -> list[ModelCallRecord]:
        records = list(self._model_chain)
        if trace_id:
            records = [r for r in records if r.trace_id == trace_id]
        return records[-limit:]

    def kinds(self) -> list[str]:
        return list(self._buffers.keys())

    def stats(self, kind: str) -> MetricStats:
        buf = self._buffers.get(kind)
        if not buf:
            return MetricStats()
        records = list(buf)
        count = len(records)
        error_count = sum(1 for r in records if r.status == "error")
        latencies = sorted(r.latency_ms for r in records)
        total = sum(latencies)
        p50 = latencies[count // 2] if count else 0.0
        p95 = latencies[min(count - 1, int(count * 0.95))] if count else 0.0
        return MetricStats(
            count=count,
            error_count=error_count,
            total_latency_ms=total,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            last_records=records[-10:],  # 只暴露最近 10 条详情
        )

    def reset(self, kind: str | None = None) -> None:
        if kind is None:
            self._buffers.clear()
            self._model_chain.clear()
        else:
            self._buffers.pop(kind, None)


# 全局实例（FastAPI lifespan 中由 AppState 持有，业务代码用 state.metrics 即可）
def new_recorder() -> MetricsRecorder:
    return MetricsRecorder()
