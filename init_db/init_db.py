"""
初始化数据库
"""

import asyncio
import logging
import re
import sys
from pathlib import Path

import asyncmy
import asyncpg
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class DBInit:
    def __init__(self, conn_conf: dict):
        self.conn_conf = conn_conf
        self.ERROR_PATTERNS = [
            re.compile(r"type.*already exists"),
            re.compile(r"relation.*already exists"),
            re.compile(r"constraint.*already exists"),
            re.compile(
                r"duplicate key value violates unique constraint.*already exists"
            ),
            re.compile(r"multiple primary keys.*not allowed"),
            re.compile(r"current transaction is aborted"),
        ]

    async def create_db(self, db_name: str):
        """创建数据库"""
        raise NotImplementedError

    async def exec_sql_file(self, db_name: str, sql_file_path: Path):
        """执行 SQL 文件"""
        raise NotImplementedError

    async def init_db(self, db_sql_mapping: dict[str, Path], max_workers: int = 5):
        """
        初始化数据库并导入数据

        Args:
            db_sql_mapping (dict[str, Path]): 数据库名称->对应的SQL文件路径
        """

        logger.info(f"开始初始化数据库 {list(db_sql_mapping.keys())}")

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}"),
            console=Console(),
        ) as progress:
            progress_queue = asyncio.Queue()  # 进度更新消息队列

            async def progress_consumer():
                """进度消费者协程，从队列中取出消息并更新进度条"""
                total = len(db_sql_mapping)
                current = 0
                task_id = progress.add_task("Start", total=total)
                while True:
                    msg = await progress_queue.get()
                    if msg is None:
                        progress_queue.task_done()
                        break
                    db_name, increment = msg
                    current += increment
                    progress.update(
                        task_id, completed=current, description=f"{db_name[:20]:20}"
                    )
                    if current >= total:
                        progress.update(task_id, description="Complete")
                    progress_queue.task_done()

            # 启动进度消费者协程
            consumer_task = asyncio.create_task(progress_consumer())

            # 信号量控制并发
            semaphore = asyncio.Semaphore(max_workers)

            async def process_database(db_name: str, sql_file_path: Path):
                """处理单个数据库的异步任务"""
                async with semaphore:
                    await self.create_db(db_name)
                    await self.exec_sql_file(db_name, sql_file_path)
                    if progress_queue:
                        await progress_queue.put((db_name, 1))

            # 并发执行任务
            tasks = [
                process_database(db_name, sql_file_path)
                for db_name, sql_file_path in db_sql_mapping.items()
            ]
            await asyncio.gather(*tasks)

            await progress_queue.put(None)  # 发送停止信号给消费者协程
            await progress_queue.join()  # 等待队列中所有任务完成
            await consumer_task  # 等待消费者协程结束

        logger.info("数据库初始化完成")


class PGInit(DBInit):
    async def create_db(self, db_name: str):
        conn = await asyncpg.connect(**self.conn_conf, database="postgres")
        try:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        except asyncpg.exceptions.DuplicateDatabaseError:
            ...
        except Exception as e:
            logger.error(f"数据库 {db_name} 创建失败: {e}")
        finally:
            await conn.close()

    async def exec_sql_file(self, db_name: str, sql_file_path: Path):
        conn = await asyncpg.connect(**self.conn_conf, database=db_name)
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                sql = f.read()
            async with conn.transaction():
                await conn.execute(sql)
        except Exception as e:
            error_msg = str(e).lower().replace("\n", " ").replace("\r", " ")
            if not any(pattern.search(error_msg) for pattern in self.ERROR_PATTERNS):
                logger.error(f"{sql_file_path.stem} 执行sql失败: {e}")
                raise
        finally:
            await conn.close()


class MyInit(DBInit):
    async def create_db(self, db_name: str):
        conn = await asyncmy.connect(**self.conn_conf, autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4")
        except Exception as e:
            if e.args[0] == 1007:
                ...
            else:
                logger.exception(f"数据库 {db_name} 创建失败: {e}")
        finally:
            conn.close()

    async def exec_sql_file(self, db_name: str, sql_file_path: Path):
        conn = await asyncmy.connect(**self.conn_conf, db=db_name)
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                sql = f.read()
            await conn.begin()
            async with conn.cursor() as cur:
                await cur.execute(sql)
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            error_msg = str(e).lower().replace("\n", " ").replace("\r", " ")
            if not any(pattern.search(error_msg) for pattern in self.ERROR_PATTERNS):
                logger.error(f"{sql_file_path.stem} 执行sql失败: {e}")
                raise
        finally:
            conn.close()


if __name__ == "__main__":
    # 数据库连接配置
    pg_init = PGInit(
        {
            "host": "127.0.0.1",
            "port": 5432,
            "user": "root",
            "password": "123321",
        }
    )
    # 数据库文件目录
    sql_dir = Path(__file__).parent / "livesqlbench" / "bird-interact-full-dumps"
    # 所有SQL文件
    sql_files = list(sql_dir.glob("*.sql"))
    # 文件名去掉 '_full.sql' 作为数据库名称
    db_sql_mapping = {f.stem.removesuffix("_full"): f for f in sql_files}
    asyncio.run(pg_init.init_db(db_sql_mapping))

    my_init = MyInit(
        {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "123321",
        },
    )
    sql_dir = Path(__file__).parent / "sales"
    sql_files = list(sql_dir.glob("*.sql"))
    # 文件名作为数据库名称
    db_sql_mapping = {f.stem: f for f in sql_files}
    asyncio.run(my_init.init_db(db_sql_mapping))
