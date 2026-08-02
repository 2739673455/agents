"""初始化数据库"""

import logging
import os
from pathlib import Path

import dotenv
import pymysql
from sqlacodegen.generators import DeclarativeGenerator
from sqlalchemy import MetaData, create_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parents[2]
ENV_FILE = ROOT_DIR / "conf" / ".env"
MYSQL_SQL_DIR = ROOT_DIR / "app" / "scripts" / "sql" / "mysql"
ENTITIES_DIR = ROOT_DIR / "app" / "entities"


class MySQLInitializer:
    """MySQL 数据库初始化器"""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        """初始化 MySQL 连接配置"""
        self._sync_db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}"
        self._conn_conf = {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password,
        }

    def delete_db(self, db_name: str) -> None:
        """删除数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self._conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = %s",
                    (db_name,),
                )
                if cur.fetchone() is None:
                    logger.info("数据库 %s 不存在，无需删除", db_name)
                    return
                cur.execute(f"DROP DATABASE `{db_name}`")
                logger.info("数据库 %s 删除成功", db_name)
        except pymysql.MySQLError:
            logger.exception("数据库 %s 删除失败", db_name)
            raise
        finally:
            if conn is not None:
                conn.close()

    def create_db(self, db_name: str) -> None:
        """创建数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self._conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = %s",
                    (db_name,),
                )
                if cur.fetchone() is not None:
                    logger.info("数据库 %s 已存在，无需创建", db_name)
                    return
                cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4")
                logger.info("数据库 %s 创建成功", db_name)
        except pymysql.MySQLError:
            logger.exception("数据库 %s 创建失败", db_name)
            raise
        finally:
            if conn is not None:
                conn.close()

    def exec_sql_file(self, db_name: str, sql_file_path: Path) -> None:
        """执行 SQL 文件"""
        sql = sql_file_path.read_text(encoding="utf-8")
        statements = [
            statement.strip() for statement in sql.split(";") if statement.strip()
        ]
        conn = None
        try:
            conn = pymysql.connect(**self._conn_conf, database=db_name)
            conn.begin()
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
            logger.info("%s 执行成功", sql_file_path.name)
        except pymysql.MySQLError:
            if conn is not None:
                conn.rollback()
            logger.exception("%s 执行失败", sql_file_path.name)
            raise
        finally:
            if conn is not None:
                conn.close()

    def gen_tb_model(self, db_name: str, output_path: Path) -> None:
        """通过反射数据库结构自动生成 SQLAlchemy ORM 模型代码"""
        engine = create_engine(f"{self._sync_db_url}/{db_name}")
        try:
            metadata = MetaData()
            metadata.reflect(engine)
            generator = DeclarativeGenerator(metadata, engine, [])
            code = generator.generate()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(code, encoding="utf-8")
            logger.info("SQLAlchemy ORM 模型代码已生成到 %s", output_path)
        finally:
            engine.dispose()


if __name__ == "__main__":
    dotenv.load_dotenv(ENV_FILE)

    db_initializer = MySQLInitializer(
        host="127.0.0.1",
        port=3306,
        user="root",
        password=os.environ["DB_META_PASSWORD"],
    )

    db_initializer.delete_db("meta")
    db_initializer.create_db("meta")
    db_initializer.exec_sql_file("meta", MYSQL_SQL_DIR / "meta.sql")

    db_initializer.delete_db("chat")
    db_initializer.create_db("chat")
    db_initializer.exec_sql_file("chat", MYSQL_SQL_DIR / "chat.sql")
