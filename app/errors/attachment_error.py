from http import HTTPStatus

from app.errors.base import ProblemError


class PathTraversalError(ProblemError):
    type = "path-traversal"
    title = "路径穿越"
    status = HTTPStatus.FORBIDDEN


class AttachmentNotFoundError(ProblemError):
    type = "attachment-not-found"
    title = "附件不存在"
    status = HTTPStatus.NOT_FOUND
