import asyncio
import functools
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine, ParamSpec, Tuple, Type, TypeVar

from config import CFG
from loguru import logger
from openai import AsyncOpenAI

P = ParamSpec("P")
R = TypeVar("R")


def async_retry(
    max_retries: int,
    timeout: float | None,
    backoff_factor: float = 1.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    异步重试装饰器

    Args:
        max_retries: 最大重试次数（默认值，可被 kwargs 中的 max_retries 覆盖）
        timeout: 单次请求超时时间（秒），None 表示不设置超时（默认值，可被 kwargs 中的 timeout 覆盖）
        backoff_factor: 退避因子，每次重试等待时间 = backoff_factor * (2 ** retry_count)
        retryable_exceptions: 可重试的异常类型
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中提取超时和重试参数，优先使用传入值
            actual_timeout = kwargs.pop("timeout", timeout)
            actual_max_retries = kwargs.pop("max_retries", max_retries)
            last_exception = None

            for attempt in range(actual_max_retries + 1):
                try:
                    if actual_timeout is None:
                        return await func(*args, **kwargs)
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=actual_timeout
                    )
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < actual_max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    raise
                except asyncio.TimeoutError:
                    if attempt < actual_max_retries:
                        wait_time = backoff_factor * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    raise TimeoutError(
                        f"Request timed out after {actual_timeout}s (retries: {actual_max_retries})"
                    )

            raise (
                last_exception
                if last_exception
                else RuntimeError("Max retries exceeded")
            )

        return wrapper

    return decorator


@async_retry(max_retries=1, timeout=None)
async def embed(text: list[str]) -> list[list[float]]:
    """嵌入文本"""
    model_config = CFG.llm.models[CFG.llm.embed_model]
    # 定义批处理大小，避免单次请求文本数量过多导致API限制
    batch_size = 64

    embedding = []  # 存储所有文本的向量表示

    # 创建 OpenAI 异步客户端，用于调用嵌入模型API
    client = AsyncOpenAI(
        base_url=model_config.base_url,  # 嵌入服务地址
        api_key=model_config.api_key,  # API密钥
    )

    # 分批处理文本，避免单次请求过大。每次处理 batch_size 个文本
    for i in range(0, len(text), batch_size):
        # 获取当前批次的文本切片
        batch_texts = text[i : i + batch_size]

        # 调用嵌入模型API，将文本转换为向量
        cur_embedding = await client.embeddings.create(
            model=model_config.model,  # 使用的嵌入模型
            input=batch_texts,  # 当前批次的文本
            encoding_format="float",  # 向量格式为浮点数
        )

        # 提取向量数据并添加到结果列表中
        # cur_embedding.data 包含了每个文本的向量信息
        embedding.extend([item.embedding for item in cur_embedding.data])
    await client.close()
    return embedding


def setup_logger():
    """配置 loguru 日志器"""
    # 避免重复配置
    if hasattr(logger, "_configured"):
        return

    # 移除默认处理器，避免重复输出
    # loguru 默认有一个输出到 stderr 的处理器，级别为 INFO
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level:^8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 控制台输出处理器
    if CFG.logging.to_console:
        logger.add(
            sink=sys.stdout,  # 输出到标准输出
            level=CFG.logging.level,  # 从配置文件读取日志级别
            format=log_format,  # 日志格式
            colorize=True,  # 启用颜色输出，提升可读性
            catch=False,  # 不捕获异常，让错误直接抛出
        )

    # 文件输出处理器
    if CFG.logging.to_file:
        log_dir = Path(__file__).parent / "logs"  # 指定日志目录
        log_dir.mkdir(parents=True, exist_ok=True)  # 确保日志目录存在

        logger.add(
            sink=log_dir / "{time:YYYY-MM-DD}.log",  # 按日期命名的日志文件
            level=CFG.logging.level,  # 使用配置的日志级别
            format=log_format,  # 日志格式
            rotation=f"{CFG.logging.max_file_size}",  # 按文件大小自动滚动
            encoding="utf-8",  # 使用UTF-8编码，支持中文
            catch=False,  # 不捕获异常，让错误直接抛出
        )

    # 标记为已配置
    setattr(logger, "_configured", True)


setup_logger()
