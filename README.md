# 使用方式
## 启动容器
- 准备 `docker/elasticsearch`
- 执行 `docker compose up -d`

## 在数据库中建表并导入数据
- 数据库表 [scripts/sql/mysql](scripts/sql/mysql)
  ```bash
  uv run scripts/init_db.py  # 初始化 meta 和 chat 数据库
  ```
- 业务数据: dbmock

## 修改配置信息
- 编辑 [conf/app_config.yaml](conf/app_config.yaml)，配置数据库和模型信息
- 编辑 [`conf/.env`](conf/.env)，配置模型服务密钥
- [conf/meta_config.yaml](conf/meta_config.yaml) 是元数据导入文件示例
- 表的 `primary_key_columns` 描述单字段或联合主键
- 字段的 `index_values` 控制是否建立字段值索引
- 表名是表元数据主键，表名和字段名共同组成字段元数据联合主键
- 外键字段通过 `reference_t_name` 和 `reference_c_name` 指向目标字段
- 指标名是指标元数据主键，`relevant_columns` 使用表名和字段名关联字段
- `meta_version` 在元数据内容变化时递增，`index_version` 记录向量索引使用的元数据版本
- 新元数据的版本为 `1`、索引版本为 `0`，版本由服务端维护，不需要写入 YAML

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
  "http://127.0.0.1:8000/api/v1/meta/import?mode=replace" \
  -F "file=@conf/meta_config.yaml"

curl "http://127.0.0.1:8000/api/v1/meta/export" -o metadata.yaml
```
