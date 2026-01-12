# 功能
## 规划

## 子代理委托
主代理通过 Task 将任务委托给子代理
子代理拥有独立状态、独立上下文。在子代理执行结束后决定将哪些内容返回总状态、总上下文

## 文件系统
- bash
- read
- edit
- write
- skill

## 状态管理
用户的 access_token 存入状态
代理将中间状态存入 .json 文件或者 sqlite 数据库
隔离不同会话间的状态文件

## 技能
https://platform.claude.com/docs/zh-CN/agents-and-tools/agent-skills/overview
### 渐进式披露
1. 技能元数据(始终加载)
SKILL.md 文件最顶端 yaml 格式的元数据，包含 name、description
2. 技能详细信息(技能触发时加载)
SKILL.md 文件所有内容
3. 资源与代码(按需加载)
附加技能目录或文件，在 SKILL.md 中引用


# Benchmark
- BIRD-SQL
    https://bird-bench.github.io/
- Spider 2.0
    https://spider2-sql.github.io/
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
