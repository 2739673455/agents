# 使用方式
## 启动容器
- 准备 `docker/elasticsearch`
- 执行 `docker compose up -d`

## 在数据库中建表并导入数据
- 数据库表 [app/scripts/sql/mysql](app/scripts/sql/mysql)
  ```bash
  uv run app/scripts/init_db.py  # 初始化 meta 和 chat 数据库
  ```
- 业务数据: dbmock

## 修改配置信息
- 编辑 [conf/app_config.yaml](conf/app_config.yaml)，配置数据库和模型信息
- 编辑 [`conf/.env`](conf/.env)，配置模型服务密钥
- 编辑 [conf/meta_config.yaml](conf/meta_config.yaml)，配置表信息

## 启动
```bash
uv sync                                                              # 安装依赖
uv run -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml  # 初始化导入元数据
uv run main.py                                                       # 启动服务
```
