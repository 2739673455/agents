import asyncio
import sys
from pathlib import Path

from config import CFG
from loguru import logger
from openai import AsyncOpenAI
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential


async def embed(
    text: list[str], retries: int = 1, timeout: float | None = None
) -> list[list[float]]:
    """嵌入文本"""

    @retry(
        stop=stop_after_attempt(retries + 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _aembed(chunk):
        async with semaphore:
            resp = await asyncio.wait_for(
                client.embeddings.create(
                    model=model_config.model, input=chunk, encoding_format="float"
                ),
                timeout=timeout,
            )
            progress.update(task_id, advance=len(chunk))
            return [i.embedding for i in resp.data]

    if not text:
        return []
    BATCH_SIZE = 64
    semaphore = asyncio.Semaphore(20)
    model_config = CFG.llm.models[CFG.llm.embed_model]
    client = AsyncOpenAI(api_key=model_config.api_key, base_url=model_config.base_url)
    chunks = [text[i : i + BATCH_SIZE] for i in range(0, len(text), BATCH_SIZE)]
    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}"),
            console=Console(),
            transient=True,
        ) as progress:  # 进度条
            task_id = progress.add_task("embedding", total=len(text))
            tasks = [_aembed(chunk) for chunk in chunks]
            results = await asyncio.gather(*tasks)
        return [emb for batch in results for emb in batch]
    finally:
        await client.close()


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
