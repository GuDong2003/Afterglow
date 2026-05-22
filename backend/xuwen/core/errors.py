"""统一异常类型与错误码。

业务异常都继承自 XuwenError，便于 chat_api 中间件统一捕获并返回结构化错误。
"""

from __future__ import annotations


class XuwenError(Exception):
    """xuwen 包的根异常。所有自定义异常都应继承自它。"""

    code: str = "xuwen.error"
    http_status: int = 500

    def __init__(self, message: str, *, detail: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - 仅调试用
        return f"[{self.code}] {self.message}"


class ConfigError(XuwenError):
    """配置缺失或非法。"""

    code = "xuwen.config"
    http_status = 500


class IngestionError(XuwenError):
    """数据导入流水线错误。"""

    code = "xuwen.ingestion"
    http_status = 422


class ParseError(IngestionError):
    """QQ JSON 解析失败。"""

    code = "xuwen.ingestion.parse"


class EmbeddingError(XuwenError):
    """向量化失败。"""

    code = "xuwen.embedding"
    http_status = 502


class StoreError(XuwenError):
    """LanceDB / 持久化层错误。"""

    code = "xuwen.store"
    http_status = 500


# 兼容别名（旧名字保留以防外部引用，建议使用 StoreError）
MemoryError_ = StoreError


class RetrievalError(XuwenError):
    """检索失败。"""

    code = "xuwen.retrieval"
    http_status = 500


class LLMError(XuwenError):
    """对话模型上游错误。"""

    code = "xuwen.llm"
    http_status = 502


class AuthError(XuwenError):
    """API key 校验失败。"""

    code = "xuwen.auth"
    http_status = 401
