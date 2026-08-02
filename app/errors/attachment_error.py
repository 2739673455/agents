from app.errors.base import NotFoundError, PermissionDeniedError


class PathTraversalError(PermissionDeniedError):
    type = "path-traversal"
    title = "路径穿越"


class AttachmentNotFoundError(NotFoundError):
    type = "attachment-not-found"
    title = "附件不存在"
