# IFLOW.md - NL2SQL 多代理系统

## 项目概述

本项目是一个基于大语言模型（LLM）的自然语言转 SQL（NL2SQL）多代理系统，旨在将用户的自然语言查询转换为可执行的 SQL 语句。该系统参考了 **BIRD-SQL** 和 **Spider 2.0** 基准测试，采用多阶段流水线架构，通过多个专业代理协同工作完成复杂的文本到 SQL 转换任务。

### 核心技术栈

| 技术                       | 用途               |
| -------------------------- | ------------------ |
| Python 3.12+               | 开发语言           |
| FastAPI                    | 元数据 API 服务    |
| OpenAI API                 | LLM 调用           |
| PostgreSQL / MySQL / Neo4j | 数据存储与向量检索 |
| OmegaConf / Pydantic       | 配置管理           |
| Jinja2                     | 提示词模板引擎     |

---

## 项目架构

```
multi-agent/
├── data_query_scripts/    # NL2SQL 查询流水线脚本
│   ├── add_context.py     # 添加上下文信息
│   ├── extend_column.py   # LLM 扩展字段名
│   ├── extend_cell.py     # LLM 扩展字段值
│   ├── recall_column.py   # 向量检索字段
│   ├── recall_cell.py     # 混合检索字段值
│   ├── recall_knowledge.py# 混合检索指标知识
│   ├── merge_col_cell.py  # 整合并过滤表和字段
│   ├── filter_tb_col.py   # LLM 过滤表和字段
│   ├── filter_knowledge.py# LLM 过滤指标知识
│   ├── add_kn_col.py      # 添加知识相关字段
│   ├── state_manage.py    # 状态管理
│   ├── util.py            # 工具函数
│   ├── config/            # 配置文件
│   └── prompts/           # 提示词模板
├── meta_db/               # 元数据数据库服务
│   ├── main.py            # FastAPI 服务入口
│   ├── query_meta.py      # 元数据查询
│   ├── save_meta.py       # 元数据保存
│   ├── config/            # 数据库配置
│   └── logs/              # 日志
├── init_db/               # 数据库初始化
│   ├── init_db.py         # 初始化脚本
│   ├── livesqlbench/      # BIRD 基准测试数据集
│   └── sales/             # 示例销售数据库
├── session/               # 会话状态存储
└── main.py                # 项目入口
```

---

## 工作流程

NL2SQL 查询流程采用流水线设计，脚本按顺序执行，结果存储到 JSON 状态文件中供后续脚本读取：

```
开始
  │
  ├── add_context         # 添加上下文信息（查询文本、关键词、日期、表信息）
  │   ├── extend_column   # LLM 生成候选字段名
  │   │   └── recall_column  # 向量检索字段
  │   │
  │   ├── extend_cell     # LLM 生成候选字段值
  │   │   └── recall_cell # 混合检索字段值
  │   │
  │   └── recall_knowledge# 混合检索指标知识
  │
  ├── merge_col_cell      # 整合字段，根据检索分数截取 top-k
  │
  ├── llm_filter_tb_col   # LLM 过滤表和字段
  │   └── llm_filter_knowledge # LLM 过滤指标知识
  │
  ├── add_kn_col          # 添加知识相关字段
  │
  ├── ┌─────────────────────────┐
  │ │  ×3 NL2SQL 并行生成      │
  │ │  ├── think               # LLM 思考分析
  │ │  ├── gen_sql             # LLM 生成 SQL
  │ │  ├── verify_sql          # LLM 校验 SQL
  │ │  ├── correct_sql         # LLM 修正错误 SQL
  │ │  └── exec_sql            # 执行 SQL
  │ └─────────────────────────┘
  │
  └── vote                # 投票选择最佳结果
       │
       └── 结束
```

---

## 配置说明

### 全局配置

- **数据查询配置**: `data_query_scripts/config/base_cfg.yml`
  - LLM 模型配置（extend_model, filter_model, nl2sql_models, vote_model）
  - 元数据服务地址
  - 最大表数量、每表最大字段数

- **元数据库配置**: `meta_db/config/base_cfg.yml`
  - Neo4j 连接配置
  - 日志配置
  - LLM 嵌入模型配置

- **数据库配置**: `meta_db/config/db_cfg/`
  - `{db_code}/db_info.yml` - 数据库连接信息
  - `{db_code}/table_info.yml` - 表结构信息
  - `{db_code}/knowledge.yml` - 指标知识定义
  - `{db_code}/skeleton.yml` - SQL 骨架示例

### 状态管理

状态文件存储在 `session/state.json`，包含以下关键字段：

| 字段                | 说明               |
| ------------------- | ------------------ |
| `db_code`           | 数据库编号         |
| `query`             | 用户查询文本       |
| `keywords`          | 提取的关键词       |
| `tb_map`            | 表信息映射         |
| `retrieved_col_map` | 检索到的字段信息   |
| `kn_map`            | 指标知识映射       |
| `filtered_col_map`  | 过滤后的字段信息   |
| `sql_results`       | SQL 生成与执行结果 |

---

## 提示词模板

所有提示词模板位于 `data_query_scripts/prompts/` 目录：

### nl2sql.yml

| 提示词名称       | 用途                                    |
| ---------------- | --------------------------------------- |
| `think_prompt`   | LLM 思考分析用户问题，规划 SQL 执行逻辑 |
| `gen_sql_prompt` | 根据思考结果生成 SQL 语句               |
| `correct_prompt` | 修正有错误的 SQL 语句                   |
| `vote_prompt`    | 从多个 SQL 结果中选择最佳答案           |

### table_rag.yml

表格检索相关的提示词模板。

---

## 开发指南

### 运行元数据服务

```bash
cd meta_db
python main.py
# 服务运行在 http://0.0.0.0:12321
```

### 执行 NL2SQL 查询流程

```bash
# 依次执行以下脚本（通过状态文件传递上下文）
python data_query_scripts/add_context.py "查询文本"
python data_query_scripts/extend_column.py
python data_query_scripts/extend_cell.py
python data_query_scripts/recall_column.py
python data_query_scripts/recall_cell.py
python data_query_scripts/recall_knowledge.py
python data_query_scripts/merge_col_cell.py
python data_query_scripts/filter_tb_col.py
python data_query_scripts/filter_knowledge.py
python data_query_scripts/add_kn_col.py
python data_query_scripts/nl2sql.py
```

### 初始化数据库

```bash
cd init_db
python init_db.py --db sales          # 初始化示例销售数据库
python init_db.py --db bird           # 初始化 BIRD 基准数据集
```

---

## API 接口

元数据服务提供以下 API 接口：

| 接口                                  | 方法 | 说明         |
| ------------------------------------- | ---- | ------------ |
| `/api/v1/metadata/health`             | GET  | 健康检查     |
| `/api/v1/metadata/save_metadata`      | POST | 保存元数据   |
| `/api/v1/metadata/get_table`          | POST | 获取表信息   |
| `/api/v1/metadata/get_column`         | POST | 获取字段信息 |
| `/api/v1/metadata/retrieve_knowledge` | POST | 检索指标知识 |
| `/api/v1/metadata/retrieve_column`    | POST | 检索字段     |
| `/api/v1/metadata/retrieve_cell`      | POST | 检索字段值   |

---

## 关键文件

| 文件                                 | 说明                                    |
| ------------------------------------ | --------------------------------------- |
| `data_query_scripts/state_manage.py` | 状态读写管理，使用文件锁确保并发安全    |
| `data_query_scripts/util.py`         | LLM 调用、提示词渲染、JSON/XML 解析工具 |
| `data_query_scripts/config.py`       | 数据查询配置加载                        |
| `meta_db/config.py`                  | 元数据库配置加载                        |
| `meta_db/main.py`                    | FastAPI 服务入口                        |
| `meta_db/query_meta.py`              | Neo4j 向量检索实现                      |

---

## 依赖安装

```bash
uv pip install -e .
```

主要依赖：
- `fastapi` / `uvicorn` - Web 服务
- `openai` - LLM 调用
- `asyncmy` / `asyncpg` - 异步数据库驱动
- `neo4j` - 图数据库
- `omegaconf` / `pydantic` - 配置管理
- `jieba` - 中文分词
- `tenacity` - 重试机制
