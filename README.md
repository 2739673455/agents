# 架构
- Planner 规划器
- Executor 执行器

# 技能
https://platform.claude.com/docs/zh-CN/agents-and-tools/agent-skills/overview
## 渐进式披露
1. 技能元数据(始终加载)
SKILL.md 文件最顶端 yaml 格式的元数据，包含 name、description
2. 技能详细信息(触发时加载)
SKILL.md 文件所有内容
3. 资源与代码(按需加载)
附加技能目录或文件，通过 SKILL.md 中的名称引用
**财务**：收入、ARR、计费 → 参阅 [scripts/demo.py](scripts/demo.py)