# 元数据
## 配置信息
### 数据库信息
```yaml
db_code: # 数据库编号
db_name: # 数据库名称
db_type: # 数据库类型
database: # 数据库
host: # 服务器地址
port: # 端口号
user: # 用户名
password: # 密码
```
### 表信息
```yaml
table:
  tb_code: # 表编号
    tb_name: # 表名
    tb_meaning: # 表含义
    # fact_or_dim: # 事实表还是维度表
    sync_col: # 同步字段值的字段，为空则同步所有字段
    no_sync_col: # 不同步字段值的字段，先获取同步字段，再从中去掉不同步的字段
    col_info: # 字段额外信息
      col1:
        col_meaning: # 字段含义
        field_meaning: # JSONB字段中每个字段的含义
        col_alias: # 字段别名
        rel_col: table.column # 关联字段

```
### 指标知识
```yaml
knowledge: # 知识
  0:
    kn_name: # 名称
    kn_desc: # 描述
    kn_def: # 定义
    kn_alias: # 别名
    rel_kn: # 相关知识
    rel_col: # 相关字段
```
### sql 骨架
```yaml
skeleton:
  - query: # 查询
    normal_query: # 标准化查询
    rel_kn: # 相关知识
    sql: # sql 语句
```

## Neo4j Schema
### 节点
- DATABASE
  - db_code # 数据库编号
  - db_name # 数据库名称
  - db_type # 数据库类型
  - database # 数据库
- TABLE
  - tb_code # 表编号
  - tb_name # 表名
  - tb_meaning # 表含义
- COLUMN
  - tb_code # 表编号
  - col_name # 字段名 (向量化)
  - col_type # 字段类型
  - col_comment # 字段注释 (向量化)
  - fewshot # 示例值 (向量化)
  - col_meaning # 字段含义 (向量化)
  - field_meaning # JSONB字段中每个字段的含义 (向量化)
  - col_alias # 字段别名 (向量化)
  - rel_col # 相关字段
- KNOWLEDGE
  - db_code # 库编号
  - kn_code # 知识编号
  - kn_name # 知识名称 (向量化)
  - kn_desc # 知识描述 (向量化)
  - kn_def # 知识定义
  - kn_alias # 知识别名 (向量化)
  - rel_kn # 相关知识
  - rel_col # 相关字段
- EMBED_COL
  - content # 嵌入内容
  - embed # 嵌入向量
- EMBED_KN
  - content # 嵌入内容
  - embed # 嵌入向量
  - tscontent # 全文搜索字段
- CELL
  - content # 嵌入内容
  - embed # 嵌入向量
  - tscontent # 全文搜索字段
### 关系
- TABLE-[BELONG]->DATABASE
- COLUMN-[BELONG]->TABLE
- COLUMN-[REL]->COLUMN
- KNOWLEDGE-[CONTAIN]->KNOWLEDGE
- KNOWLEDGE-[REL]->COLUMN
- EMBED_COL-[BELONG]->COLUMN
- EMBED_KN-[BELONG]->KNOWLEDGE
- CELL-[BELONG]->COLUMN

# 流程
```mermaid
graph TB
  start[开始]
  add_context[添加上下文信息 <font size=2 color=gray>
    查询文本 关键词 日期信息 表信息 表说明]
  extend_column[LLM扩展字段 <font size=2 color=gray>
    生成候选字段名]
  extend_cell[LLM扩展字段值 <font size=2 color=gray>
    生成候选字段值]
  recall_column[向量检索字段]
  recall_cell[混合检索字段值]
  recall_knowledge[混合检索指标知识]
  merge_col_cell[整合表字段字段值，并根据检索分数截取topk表和字段 <font size=2 color=gray>
    先按相似度分数过滤每个表的字段
    再将每张表字段分数之和作为表分数过滤表]
  llm_filter_tb_col[LLM过滤表和字段 <font size=2 color=gray>
    先分批过滤表
    再逐表过滤单表所有字段]
  llm_filter_knowledge[LLM过滤指标知识 <font size=2 color=gray>
    过滤相关指标知识]
  add_kn_col[添加知识相关字段 <font size=2 color=gray>
    获取指标知识的相关字段
    将其与召回的字段整合]
  vote[投票]
  bye[结束]

  subgraph nl2sql [×3]
    direction TB

    think[LLM思考]
    gen_sql[LLM生成sql]
    verify_sql[LLM校验sql <font size=2 color=gray>
      explain]
    correct_sql[LLM修正sql]
    exec_sql[执行sql]

    think --> gen_sql
    gen_sql --> verify_sql
    verify_sql -.-> |有误| correct_sql
    verify_sql -.-> |无误| exec_sql
    correct_sql --> exec_sql
  end

  start --> add_context
  add_context --> extend_column
  add_context --> extend_cell
  extend_column --> recall_column
  extend_cell --> recall_cell
  add_context --> recall_knowledge
  recall_column --> merge_col_cell
  recall_cell --> merge_col_cell
  merge_col_cell --> llm_filter_tb_col
  recall_knowledge --> llm_filter_knowledge
  llm_filter_tb_col --> add_kn_col
  llm_filter_knowledge --> add_kn_col
  add_kn_col --> nl2sql
  add_kn_col --> nl2sql
  add_kn_col --> nl2sql
  nl2sql --> vote
  nl2sql --> vote
  nl2sql --> vote
  vote --> bye
```
