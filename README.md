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
- [conf/meta_config.yaml](conf/meta_config.yaml) 是元数据导入文件示例
- 表的 `primary_key_columns` 描述单字段或联合主键
- 字段的 `index_values` 控制是否建立字段值索引
- 外键字段通过 `reference_column_id` 指向目标字段

## 启动
```bash
uv sync         # 安装依赖
uv run main.py  # 启动服务
```

## 导入和导出元数据
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/meta/import?mode=merge" \
  -F "file=@conf/meta_config.yaml"

curl -X POST \
  "http://127.0.0.1:8000/api/v1/meta/import?mode=replace&confirm=true" \
  -F "file=@conf/meta_config.yaml"

curl "http://127.0.0.1:8000/api/v1/meta/export" -o metadata.yaml
```
