"""元数据业务错误"""

from app.errors.base import ConflictError, NotFoundError, ValidationError


class InvalidMetadataError(ValidationError):
    type = "invalid-metadata"
    title = "元数据校验失败"


class MetadataNotFoundError(NotFoundError):
    type = "metadata-not-found"
    title = "元数据不存在"


class MetadataConflictError(ConflictError):
    type = "metadata-conflict"
    title = "元数据冲突"
