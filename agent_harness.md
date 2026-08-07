### Q1：你怎么理解 AI Agent 里的 Harness？

**Harness 是模型外部的一层 Agent 运行与控制系统**。

Anthropic 对 Harness 有两个很有代表性的描述：

- 一个比较宽的定义是：**Agent Harness / Scaffold 是让一个模型能够作为 Agent 行动的系统**，它负责处理输入、编排工具调用并返回结果。
- 在安全视角下，Anthropic 又把 Harness 描述为模型运行时所受的**指令和 Guardrails**，也就是告诉模型应该怎么做、什么不能做、哪些动作需要确认。

OpenAI 在 Agents SDK 中使用了 **model-native harness** 这个说法，强调 Harness 让 Agent 能够在计算机环境中跨文件、跨工具工作，同时配合 Sandbox 执行长周期任务。

LangChain 对 Harness 的定义更偏工程化，它把 Agent Harness 描述成一种 **opinionated、batteries-included 的 Agent Framework**，在基本 Tool Calling Loop 的基础上预置文件系统、上下文管理、任务委派、Subagent、长任务能力等。

所以综合来看，可以将 Harness 定义为：

> **Harness 是包在模型或 Agent Loop 外面的工程控制层。它负责决定模型拿到什么上下文、能调用什么工具、状态如何保存、复杂任务如何拆解、什么时候需要人工确认、长上下文怎么压缩、结果和中间产物存在哪里，以及失败后怎么恢复。它把“会推理的模型”变成“可执行、可控制、可持续运行的 Agent”。**

一个比较完整的 Harness 可以拆成下面几个部分：

1. **Instruction / Prompt Control**：系统提示词、工具说明、规则。
2. **Context Management**：历史上下文、摘要压缩、Context Offloading、Memory、Skills。
3. **Tool Orchestration**：工具注册、选择、调用、结果处理。
4. **State / Persistence**：任务状态、会话状态、Checkpoint、跨会话 Memory。
5. **Planning / Delegation**：任务拆解、Todo、Subagent、多 Agent 协作。
6. **Execution Environment**：Filesystem、Sandbox、代码执行、工作目录。
7. **Guardrails / Permissions**：权限、白名单、参数校验、HITL、危险动作审批。
8. **Recovery / Reliability**：重试、错误修复、中断恢复、降级。
9. **Observability / Evaluation**：Trace、日志、事件流、评测、Bad Case。
10. **Artifact Management**：中间文件、报告、代码、CSV、Markdown、PDF 等产物管理。

### Q1 追问：为什么现在大家越来越强调 Harness？

Agent 的能力同时取决于模型和外部 Harness。

同一个模型：

- Tool Description 不一样；
- 上下文组织方式不一样；
- 有没有 Memory；
- 有没有 Subagent；
- 有没有文件系统；
- 有没有验证和重试；
- 权限边界不一样；

最后表现可以差很多。

所以现在做 Agent 工程，需要考虑完整链路：

```text
                  ┌──────────── Harness ────────────┐
                  │                                 │
User -> Context -> Model -> Plan -> Tool -> Result -> Verify -> Answer
         ↑          │       │       │       │
         │          │       │       │       └─ Artifact / State
         │          │       │       └─ Permission / Sandbox
         │          │       └─ Subagent / Planning
         │          └─ Prompt / Tool Policy
         └─ Memory / Summary / Retrieval
                  │
                  └──────────────────────────────────┘
```

### Q2：Deep Agents 为什么被称为 Agent Harness？

它底层仍然使用 LangChain 的 Agent 基础抽象和 LangGraph Runtime，但是在基础 Tool Calling Loop 上面，提前实现了一套适合复杂长任务的 Harness。

Deep Agents 的 Harness 实现可以分成四大类：

1. **Execution Environment**
   - Tools / MCP；
   - Virtual Filesystem；
   - Pluggable Backend；
   - Filesystem Permissions；
   - Sandbox / Code Execution；
   - Streaming。

2. **Context Management**
   - Skills；
   - Memory；
   - Summarization；
   - Large Tool Result Offloading；
   - Prompt Caching。

3. **Delegation**
   - Subagent；
   - `task` 工具；
   - 独立 Context Window；
   - Async Subagent；
   - Task Planning（当前是可选能力）。

4. **Steering / Safety**
   - Human-in-the-loop；
   - Interrupt；
   - Filesystem Permission；
   - Tool Approval。

Deep Agents 的实现机制包括：

> **Middleware + Backend + Harness Profile。**

Deep Agents 通过 Middleware 控制上下文、Tool Call 和状态，通过 Backend 抽象存储和执行环境，再通过 Harness Profile 针对不同模型调整 Prompt、工具描述和 Middleware。

Deep Agents 可以挂自定义 Tool，也可以接 MCP。

Tool 决定 Agent 能做什么。

例如：

```text
search
database_query
read_file
write_file
fetch_url
send_email
...
```

Harness 负责向模型提供 Tool，并控制 Tool 的暴露方式、Tool Description 和结果返回模型上下文的方式。

Deep Agents 默认提供文件系统能力，例如：

```text
ls
read_file
write_file
edit_file
delete
glob
grep
```

文件系统可以保存复杂 Agent 的中间信息，减少 Message Context 占用。

例如一个 Research Agent 搜了几十个网页，更合理的方式是：

```text
Web Search
   ↓
把大结果保存到文件
   ↓
主 Context 只保存：
"详细搜索结果已保存到 /workspace/search_1.md"
```

Deep Agents 把文件系统和存储进一步抽象成 Backend。

Backend 包括：

```text
StateBackend
FilesystemBackend
StoreBackend
Sandbox Backend
CompositeBackend
Custom Backend
```

Backend 决定：

- 文件存在内存还是磁盘；
- 是否跨 Thread 持久化；
- Memory 放在哪里；
- 是否允许执行 Shell；
- 不同目录是否路由到不同存储。

可以配置：

```text
read
write
allow
deny
```

例如：

```text
/workspace/** -> 允许读写
/.env         -> 禁止读取
/secret/**    -> 禁止访问
```

使用 Sandbox Backend 时，可以给 Agent 暴露 `execute`：

```text
Agent
  ↓
execute("pytest")
execute("python analysis.py")
execute("git diff")
```

Harness 的关键作用是给模型提供隔离、可控的执行环境。

长任务执行时间越长，Message History 越大。

Deep Agents 会通过 Summarization Middleware 压缩旧消息：

```text
旧历史：
message1
message2
...
message100

        ↓ Summarize

summary
message91
...
message100
```

从而延长 Agent 可以持续工作的时间。

工具返回特别大时，不一定全部塞给模型。

可以：

```text
large tool result
      ↓
filesystem/backend
      ↓
context 中只保留摘要 + 文件地址
```

Deep Agents 支持通过 `AGENTS.md` 等文件加载持久化 Memory。

Memory 内容包括：

```text
用户偏好
项目规则
代码规范
业务约束
历史经验
```

Memory 可以跨会话存在。

Skills 更像：

> **按需加载的 SOP / 专业能力包。**

例如：

```text
/skills/
    research/
        SKILL.md
    attribution/
        SKILL.md
    ppt/
        SKILL.md
```

Agent 启动时不需要把所有 Skill 的全文放进 Context，只读取必要元信息，需要时再加载具体 Skill。

对于支持 Prompt Cache 的 Provider，稳定的系统提示词、Memory、Skill 等内容可以被缓存。

目的主要是：

- 降低重复 Token 处理；
- 降低延迟；
- 降低成本。

Deep Agents 默认可以通过 `task` 工具把工作交给 Subagent。

例如：

```text
Main Agent
   │
   ├─ Research Agent
   ├─ Database Agent
   └─ Document Agent
```

Subagent 可以实现 **Context Isolation**。

假设 Research Agent 做了：

```text
20 次搜索
10 次网页读取
5 次文件处理
```

主 Agent 不一定需要看到所有 Tool Call。

它最终可能只收到：

```text
Research Agent Final Result:
- 结论 A
- 结论 B
- 引用 C
```

这样主 Agent 的上下文不会被大量中间过程污染。

当前 Deep Agents 会默认增加一个通用同步 Subagent，主 Agent 可以通过 `task` 工具调用。

也可以定义专用 Subagent：

```text
researcher
sql-agent
reviewer
code-agent
```

不同 Subagent 可以拥有不同：

- Prompt；
- Model；
- Tools；
- Skills；
- Middleware；
- Interrupt Policy。

Deep Agents 仍然支持 Todo Planning：

```text
pending
in_progress
completed
```

对应 `write_todos`。

但面试时建议注意版本：

> **从 Deep Agents v0.7 起，Task Planning 是 opt-in，不再属于默认 Harness。**

需要显式加入 `TodoListMiddleware`。

例如：

```text
read_file     -> 自动执行
write_file    -> 需要审批
delete_file   -> 需要审批
send_email    -> 需要审批
```

Harness 可以在模型调用 Tool 后、真正执行之前中断：

```text
Model 决定执行
    ↓
Harness Interrupt
    ↓
Human Review
    ↓
Approve / Edit / Reject
    ↓
继续执行
```

> 模型提出动作，但最终是否执行由 Harness 决定。

当前 Deep Agents 的 Bare Stack 包括：

```text
FilesystemMiddleware
        ↓
SubAgentMiddleware
        ↓
SummarizationMiddleware
        ↓
PatchToolCallsMiddleware
        ↓
Prompt Caching
        ↓
Harness Profile
```

可选能力会继续插入：

```text
SkillsMiddleware
MemoryMiddleware
AsyncSubAgentMiddleware
HumanInTheLoopMiddleware
Custom Middleware
...
```

Middleware 的价值是：

> **不修改核心 Agent Loop，也可以改变 Agent 的上下文、工具、状态和执行行为。**

Deep Agents 还做了 Harness Profile。

不同模型需要与之匹配的：

```text
System Prompt
Tool Description
Tool 数量
Middleware
Subagent Prompt
```

所以可以针对：

```text
OpenAI
Anthropic
具体 Model
```

定义不同的 Harness Profile。

Profile 可以调整：

- system prompt；
- tool descriptions；
- excluded tools；
- excluded middleware；
- extra middleware；
- general-purpose subagent。

### Q：掌柜智库 / RAG 知识库项目哪些地方体现了 Harness？

项目基于 **RAG + LangGraph Workflow**，Harness 能力主要体现在以下五个方面。

导入链路和查询链路都使用 LangGraph State：

```text
ImportGraphState
QueryGraphState
```

把：

```text
original_query
session_id
task_id
is_stream
item_names
rewritten_query
...
```

放到 State 中，在多个节点之间传递。

LangGraph State 为 Harness 提供状态基础。

查询时会结合历史会话和当前 Query：

```text
MongoDB 历史会话
      +
当前 Query
      ↓
LLM
      ↓
商品名抽取 + Query Rewrite
```

商品确认成功以后：

```text
item_names
rewritten_query
```

继续写入 State。

如果之前历史消息里商品名不完整，还会做回填。

具体包括：

- Conversation Context；
- Entity State；
- Query Rewrite；
- Context Enrichment。

属于 Harness 中的 Context Management 思路。

查询阶段由系统控制多路信息源，为模型组织回答所需的上下文：

```text
Vector Search
HyDE Search
MCP Web Search
      ↓
RRF
      ↓
Rerank
      ↓
动态截断
      ↓
LLM
```

MCP 网络检索提供外部 Tool Access。

> **模型只负责其中部分决策或生成，真正可以进入 Context 的信息由工程链路控制。**

商品名称的抽取结果还需要进一步校验。

后面还会：

```text
商品名 -> Embedding -> 商品向量库匹配
```

然后根据匹配结果：

```text
高分 -> 直接确认
中间分 -> 返回候选，让用户确认
低分 -> 让用户补充商品名称
```

> 模型先提出一个判断，系统再通过可验证数据做校验，不确定就进入澄清。

项目还设置了低置信度过滤：

```text
Rerank 分低
    ↓
过滤上下文
    ↓
如果全部被过滤
    ↓
拒答
```

项目有：

```text
task_id
节点进度
SSE
Trace 日志
Prometheus
Grafana
```

并且在 Milvus、LLM、MCP 出错时设计了：

```text
重试
空结果
备用召回源
备用模型
兜底话术
```

### Q：掌柜问数 / Text2SQL 项目哪些地方体现了 Harness？

项目在模型外设置了完整的控制系统。

项目先建设 Metadata Knowledge Base：

```text
MySQL
  ├─ 表
  ├─ 字段
  └─ 指标

Qdrant
  ├─ 字段向量
  └─ 指标向量

Elasticsearch
  └─ 字段取值
```

用户问题进入后分别召回：

```text
字段
指标
字段值
```

再做：

```text
补全
按表分组
精筛
```

最后只给模型：

> **生成 SQL 真正需要的最小充分 Context。**

Harness 控制模型生成 SQL 前能够看到哪些 Schema。

在 SQL 生成前先让模型识别：

```text
时间范围
指标
过滤条件
维度
实体
```

如果存在歧义：

```text
Harness -> 先澄清用户
```

存在歧义时会先澄清用户，确认后再执行。

数据库权限由系统统一控制。

系统分别控制：

```text
Metadata Retrieval
SQL Generation
SQL Parser
EXPLAIN
Permission Service
SQL Executor
```

模型主要负责：

```text
语义理解
SQL 生成
部分语义检查
```

真实数据库动作由工具和代码执行。

SQL 生成后依次执行：

```text
SQL Parse
EXPLAIN
Permission Check
Security Check
LLM Semantic Check（扩展方案）
Result Reflection（扩展方案）
```

包括检查：

```text
指标口径
GROUP BY 粒度
过滤条件
JOIN
时间范围
```

模型生成的 SQL 必须通过校验后才能执行。

生成 SQL 之前：

```text
user_id
+
需要访问的表
      ↓
权限接口
```

返回：

```text
表级权限
行级过滤条件
```

然后系统把行级条件强制追加到 SQL。

执行 Tool 本身还限制：

```text
只允许查询
不允许写操作
```

如果 SQL 出错：

```text
原问题
生成 SQL
错误信息
Metadata Context
      ↓
Correction Node
      ↓
重新生成 / 局部修复
```

为了防止死循环：

```text
最大重试次数
错误类型判断
权限错误直接中断
危险 SQL 直接中断
多次失败 -> 澄清 / 转人工
```

项目把历史正确 SQL 检索出来：

```text
Query
  ↓
召回相似历史 SQL
  ↓
2～5 个 Few-shot
  ↓
Prompt
```

还设计了：

```text
用户纠正 SQL
    ↓
进入 Few-shot Example Library
```

历史正确 SQL 与用户纠正 SQL 共同构成 Experience Memory / Learning Loop。

### Q：电商小二 / AI 客服项目哪些地方体现了 Harness？

项目通过以下能力控制业务流程：

```text
任务状态
轨道校验
流程白名单
信息槽
```

每个用户维护独立状态：

```text
历史消息
当前任务
已收集槽位
当前订单
当前商品
挂起任务
```

如果用户在查物流时突然问客服电话：

```text
当前物流任务
     ↓
挂起
     ↓
处理临时问题
     ↓
恢复原任务
```

> **Stateful Agent + Interrupt / Resume。**

项目采用以下职责划分：

```text
LLM
 ├─ 意图理解
 ├─ 参数抽取
 └─ 结构化规划

Code / Workflow / API
 └─ 真正执行业务
```

例如退款：

```text
用户："帮我退款"
       ↓
LLM 识别退款意图
       ↓
收集订单号 / 原因
       ↓
业务规则验证
       ↓
退款接口判断
       ↓
满足条件才执行
```

模型没有退款权限。

> **Model proposes，Harness decides / executes。**

模型的 JSON 可能格式合法，但内容仍不可执行，例如：

```text
同时命中任务 + 知识
编造不存在的 Flow
一次开启多个 Flow
```

所以做统一 Validator：

```text
只能命中一个方向？
        ↓
Flow 是否存在？
        ↓
Command 是否在白名单？
        ↓
是否重复开启多个流程？
        ↓
知识类型是否存在？
        ↓
上下文是否完整？
```

失败就：

```text
停止执行
+
向用户澄清
```

模型只能从系统注册的以下能力中选择：

```text
Flow
Command
Business API
```

这些能力构成 Tool Registry + Tool Allowlist。

每个业务 Flow 配置：

```text
需要哪些信息
每一步追问
接口
结果判断
失败兜底
转人工规则
```

例如修改地址：

```text
order_id
new_address
contact_name
phone
```

如果 Slot 不完整：

```text
Harness -> 继续询问用户
```

缺失的 Slot 必须由用户补充确认。

> 高风险动作不会由大模型直接决定。

例如：

```text
退款
订单修改
转人工
```

需要：

```text
业务规则
接口真实返回
用户归属校验
白名单
```

遇到：

```text
特殊退款
投诉
复杂异常
无法确认
用户主动要求
```

会转人工。

项目有：

```text
RAGAS
真实测试集
线上高频问题
日志
任务完成率
问题解决率
转人工率
Bad Case
```

### Q：市场罗盘 / DeepAgents 深度搜索项目哪些地方实现了 Harness？

项目直接使用 DeepAgents 创建主 Agent，并具备以下能力：

```text
Planning / Coordination
Subagents
Tools
Filesystem / Workspace
Long-running execution
Artifact generation
Context isolation
Streaming / Observability
```

主 Agent 负责：

```text
理解需求
拆解任务
决定数据源
调度 Subagent
检查是否需要补充搜索
最终汇总
```

主 Agent 专注于协调工作。

项目按数据源拆了多个 Subagent：

```text
Main Agent
   │
   ├── Web Search Agent
   │      └─ 公开网络信息
   │
   ├── Database Agent
   │      ├─ 查看表
   │      ├─ Preview
   │      └─ SQL Query
   │
   └── Knowledge Base Agent
          └─ 企业内部资料
```

价值包括：

- 专业 Prompt；
- 不同 Tool；
- 独立 Context；
- 主 Agent 不被大量检索细节污染。

项目工具层包括：

```text
Web Search
Database Tools
File Read
Markdown Generate
PDF Convert
```

所以 Agent 可以完成以下操作：

```text
获取信息
执行查询
读取用户文件
生成交付物
```

每个任务创建独立会话目录：

```text
/session_x/
    upload/
    data/
    research/
    report.md
    report.pdf
```

复杂任务的中间结果和最终报告都落在 Workspace 中。

文件系统把 Context 从 Message 扩展到工作空间，成为 Agent 的扩展工作记忆。

在 Subagent 隔离的基础上，服务端通过：

```text
ContextVar
```

保存：

```text
session_id
session_directory
```

避免并发用户：

```text
文件串目录
消息推错连接
上下文互相覆盖
```

子 Agent 返回结果后，主 Agent 会继续判断：

```text
信息够了吗？
   │
   ├─ 否 -> 补充搜索 / 再查数据库
   └─ 是 -> 生成报告
```

关键事件都会通过 WebSocket 推到前端：

```text
Tool Start
Tool Finish
Subagent Start
Subagent Finish
Workspace Created
Task Finished
```

用户可以看到：

```text
正在搜索
正在查数据库
正在生成文件
已完成
```

### Q：归因分析项目哪些地方体现了 Harness？

归因分析项目结合 Skill、Tool、Workspace 和 Long Context Management，为模型提供完整的分析工作环境和 SOP。

项目定义了：

```text
归因分析 Skill
```

Skill 要求 Agent 按固定分析思想推进：

```text
指标理解
   ↓
基线对比
   ↓
规模拆解
   ↓
效率拆解
   ↓
结构拆解
   ↓
贡献拆解
   ↓
异常识别
   ↓
报告
```

> Skill 为模型提供分析方法和约束，模型据此决定具体的工具调用和任务拆解方式。

业务数据不由模型凭空生成。

Agent 调：

```text
Data Query Tool
      ↓
Text2SQL Service
      ↓
SQL Validation
      ↓
Query
      ↓
CSV / JSON
```

Agent 再基于落盘的数据继续分析。

数据获取和分析链路如下：

```text
Model -> Request Data
Harness/Tool -> Real Data
Model -> Analyze Real Data
```

以下内容全部进入当前会话 Workspace：

```text
用户附件
数据文件
中间分析文件
最终报告
```

Workspace 中可以保存：

```text
raw.csv
clean.csv
channel_summary.csv
product_summary.csv
report_data.json
report.html
```

文件落盘让 Prompt 只保留必要的数据引用和摘要。

项目实现了长上下文压缩。

核心结构：

```text
MySQL
 ├─ Conversation
 ├─ Messages
 └─ Context Compression Records
```

每条消息有：

```text
context sequence
```

当 Agent 产生摘要事件：

```text
旧消息
   ↓
Summary
   ↓
保存压缩记录
```

会话恢复时：

```text
summary + recent messages
```

替代全部历史。

项目持久化：

```text
User Message
Model Message
Tool Call
Tool Result
```

因此长任务中途断开，不至于全部丢失。

用户后续问：

```text
“刚才那个渠道再拆一下”
“把商品维度也加进去”
```

Agent 仍然知道：

```text
之前分析目标
指标口径
数据文件
中间结论
```

原因是：

```text
Message Persistence
+
Summary
+
Workspace
```

共同构成 Context。

文件返回 Tool 会校验：

```text
文件必须位于当前 Workspace
```

避免 Path Escape。

最终交付包括：

```text
自然语言结论
CSV
JSON
中间分析文件
HTML Report
```

最终交付由 Harness 统一管理。

### Q：舆情分析项目哪些地方体现了 Harness？

舆情分析项目采用 **Multi-Agent / Multi-module Orchestration**，由外层服务负责启动、协调、通信、状态和最终产物。

项目同时运行三个分析模块：

```text
                   Orchestrator
                       │
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
 本地舆情分析      媒体报道分析       事实核验
       │               │                │
       └───────────────┼────────────────┘
                       ↓
                  Final Report
```

三路分别负责：

```text
用户讨论
公开媒体
权威事实
```

每个分析模块内部都会：

```text
生成报告结构
      ↓
逐段搜索
      ↓
生成摘要
      ↓
Reflection
      ↓
补充搜索
      ↓
保存报告
```

每个模块通过多步骤流程持续研究，外层 Harness 负责保障整个流程运行。

三个模块通过 Event Bus 解耦通信：

```text
Event Bus
```

发布：

```text
progress
summary
result
error
```

其他组件订阅。

Event Bus 实现 Event-driven Coordination。

三个模块产出阶段摘要以后：

```text
Summary Events
     ↓
累计一定数量
     ↓
Moderator LLM
     ↓
生成 Discussion Conclusion
```

Moderator 生成的结论构成 Shared Team Context，供后续研究 Worker 参考：

```text
Shared Team Context
```

SSE 会把 Event Bus 的事件推给前端。

同时保存：

```text
Progress Buffer
Result Buffer
```

用户断线重连以后可以回放。

三个模块分别落盘：

```text
local_sentiment_report.md
media_report.md
fact_check_report.md
discussion.log
```

最终 Report Generator 读取以下落盘产物：

```text
3 个 Report
+
Discussion Log
```

再生成最终报告。

> Agent / Worker 之间通过稳定产物协作，Prompt 只保留必要上下文。
