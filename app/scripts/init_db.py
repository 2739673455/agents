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

PROJECT_DIR = Path(__file__).parents[2]
ENV_FILE = PROJECT_DIR / "conf" / ".env"
MYSQL_SQL_DIR = PROJECT_DIR / "app" / "scripts" / "sql" / "mysql"
ENTITIES_DIR = PROJECT_DIR / "app" / "entities"


class DBInit:
    """数据库初始化器"""

    def check_db_exists(self, db_name: str) -> bool:
        """检查数据库是否存在"""
        raise NotImplementedError

    def delete_db(self, db_name: str) -> None:
        """删除数据库"""
        raise NotImplementedError

    def create_db(self, db_name: str) -> None:
        """创建数据库"""
        raise NotImplementedError

    def exec_sql_file(self, db_name: str, sql_file_path: Path) -> None:
        """执行 SQL 文件"""
        raise NotImplementedError

    def get_sync_db_url(self, db_name: str) -> str:
        """获取同步数据库连接 URL"""
        raise NotImplementedError

    def init_db(self, db_name: str, sql_file_path: Path) -> None:
        """建库建表，执行 SQL 文件"""
        logger.info("开始初始化数据库 %s", db_name)

        if self.check_db_exists(db_name):
            self.delete_db(db_name)
        self.create_db(db_name)
        self.exec_sql_file(db_name, sql_file_path)

        logger.info("数据库 %s 初始化完成", db_name)

    def gen_tb_model(self, db_name: str, output_path: Path) -> None:
        """通过反射数据库结构自动生成 SQLAlchemy ORM 模型代码"""
        engine = create_engine(self.get_sync_db_url(db_name))
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


class MyInitializer(DBInit):
    """MySQL 数据库初始化器"""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        """初始化 MySQL 连接配置"""
        self._auth = f"{user}:{password}@{host}:{port}"
        self.conn_conf = {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password,
        }

    def check_db_exists(self, db_name: str) -> bool:
        """检查数据库是否存在"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = %s",
                    (db_name,),
                )
                result = cur.fetchone()
                return result is not None
        except pymysql.MySQLError:
            logger.exception("检查数据库 %s 是否存在时失败", db_name)
            raise
        finally:
            if conn is not None:
                conn.close()

    def delete_db(self, db_name: str) -> None:
        """删除数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE `{db_name}`")
        except pymysql.MySQLError:
            logger.exception("删除数据库 %s 时失败", db_name)
            raise
        finally:
            if conn is not None:
                conn.close()

    def create_db(self, db_name: str) -> None:
        """创建数据库"""
        conn = None
        try:
            conn = pymysql.connect(**self.conn_conf, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4")
        except pymysql.MySQLError:
            logger.exception("创建数据库 %s 时失败", db_name)
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
            conn = pymysql.connect(**self.conn_conf, database=db_name)
            conn.begin()
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
        except pymysql.MySQLError:
            if conn is not None:
                conn.rollback()
            logger.exception("执行 SQL 文件 %s 时失败", sql_file_path.stem)
            raise
        finally:
            if conn is not None:
                conn.close()

    def get_sync_db_url(self, db_name: str) -> str:
        """获取同步数据库连接 URL"""
        return f"mysql+pymysql://{self._auth}/{db_name}"


if __name__ == "__main__":
    dotenv.load_dotenv(ENV_FILE)

    db_initializer = MyInitializer(
        host="127.0.0.1",
        port=3306,
        user="root",
        password=os.environ["DB_META_PASSWORD"],
    )

    db_initializer.init_db("meta", MYSQL_SQL_DIR / "meta.sql")

    db_initializer.init_db("chat", MYSQL_SQL_DIR / "chat.sql")
