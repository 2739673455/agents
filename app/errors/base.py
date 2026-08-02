"""应用异常与 RFC 9457 Problem Details 响应模型"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any


class ProblemError(Exception):
    """可由全局处理器转换为 Problem Details 响应的应用异常"""

    type: str = "internal-server-error"
    title: str = "服务器内部错误"
    status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self,
        title: str | None = None,
        *,
        detail: str | None = None,
        type: str | None = None,
        status: int | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> None:
        self.title = title or self.title
        self.detail = detail
        self.extensions = dict(extensions or {})
        if type is not None:
            self.type = type
        if status is not None:
            self.status = status

        super().__init__(detail or self.title)

    def to_problem(
        self,
        *,
        instance: str | None = None,
    ) -> dict[str, Any]:
        """转换为响应体"""
        payload: dict[str, Any] = dict(self.extensions)
        payload.update(
            {
                "type": self.type,
                "title": self.title,
                "status": self.status,
            }
        )

        if self.detail is not None:
            payload["detail"] = self.detail
        if instance:
            payload["instance"] = instance
        return payload


class InternalServerError(ProblemError):
    type = "internal-server-error"
    title = "服务器内部错误"
    status = HTTPStatus.INTERNAL_SERVER_ERROR


class ValidationError(ProblemError):
    type = "validation-error"
    title = "参数校验失败"
    status = HTTPStatus.UNPROCESSABLE_ENTITY


class PermissionDeniedError(ProblemError):
    type = "permission-denied"
    title = "权限不足"
    status = HTTPStatus.FORBIDDEN


class NotFoundError(ProblemError):
    type = "not-found"
    title = "资源不存在"
    status = HTTPStatus.NOT_FOUND


class ConflictError(ProblemError):
    type = "conflict"
    title = "资源冲突"
    status = HTTPStatus.CONFLICT
