# Anti-Hallucination Pipeline Design

## Goal

为现有多智能体售后系统增加一条“证据优先、审查兜底、可降级不硬拦截”的防幻觉回答链路，优先覆盖：

- 知识库 / RAG 类回答
- 高风险事实性结论
- 高风险维修建议与诊断结论

系统在证据充分时正常回答并展示证据卡片；在证据不足时允许继续回答，但必须明确标注“不确定”，并解释证据不足原因。

## Why This Matters

当前项目已经具备一些与幻觉控制相关的基础能力：

- 知识库查询入口：`backend/app/infrastructure/tools/local/knowledge_base.py`
- 多智能体编排：`backend/app/services/agent_service.py`
- 结构化输出归一：`backend/app/services/structured_output_service.py`
- 会话记忆与上下文压缩：`backend/app/services/memory_service.py`、`backend/app/services/context_compression_service.py`
- 工具失败分类与任务状态跟踪：现有 `tool_failure_service`、`task_memory_service`

但当前仍缺少一条真正针对“事实正确性”的治理链路：

- 没有把答案与证据绑定
- 没有“证据不足时自动降级”的机制
- 没有单独的事实审查角色
- 没有可量化的防幻觉评测指标

因此，这次设计不是“再加一个 RAG 功能”，而是把项目升级为“具备证据归因、审查判定、降级输出、评测闭环”的可解释问答系统。

## Scope

本次设计聚焦一个可独立落地的子项目，不扩展到所有类型回答。

### In Scope

- 对知识库 / RAG 类回答增加证据绑定
- 对高风险结论增加审查 agent 二次核验
- 对最终回答增加证据卡片
- 在证据不足时自动改写为不确定回答
- 增加结构化审查结果
- 增加最小可用评测集与评测指标

### Out of Scope

- 对所有普通闲聊回答做全量审查
- 多模型投票、复杂 reranker、在线学习
- 前端重做整页交互
- 通用安全/合规审核平台

## Recommended Approach

采用“两阶段回答链路 + 审查后处理”的方案：

1. 检索阶段：知识库返回答案候选所需的证据片段和元数据
2. 生成阶段：主 agent 生成候选答案，而不是直接生成最终答案
3. 审查阶段：新增 review agent / verifier service，对候选答案与证据进行一致性核验
4. 输出阶段：根据审查结论决定正常放行还是降级为不确定回答，并组装证据卡片

这是当前项目里性价比最高的方案：

- 比“只显示引用”更强，因为它能主动识别证据不足
- 比“全量复杂审查框架”更可控，因为接入点清晰、范围聚焦
- 能以较小改动接入现有多 agent 架构，而不是推翻重来

## Architecture

### High-Level Flow

```text
User Query
  -> Orchestrator / Domain Agent
  -> Knowledge Retrieval (if triggered)
  -> Candidate Answer + Risk Label + Evidence References
  -> Review Agent / Answer Verifier
  -> Verdict (supported / partial / unsupported / conflict)
  -> Post-processor
  -> Final Answer + Evidence Card + Uncertainty Reason
```

### New Components

建议新增 4 个逻辑组件：

1. `retrieval_evidence_service`
   统一封装知识库检索结果，输出标准化 evidence 列表

2. `risk_classification_service`
   识别当前回答是否属于高风险回答

3. `answer_review_service`
   调用审查 agent，基于候选答案和证据给出结构化 verdict

4. `answer_postprocess_service`
   负责最终回答降级、证据卡片组装、对前端输出统一结构

## Risk Definition

第一版高风险判定采用规则优先，不引入复杂分类模型。

### High-Risk Categories

- 维修/诊断结论
  - 例如“这是主板故障”
  - 例如“只要重装系统就能解决”

- 知识库事实性回答
  - 例如“某型号支持什么功能”
  - 例如“某售后流程标准步骤是什么”

- 带明确行动建议的回答
  - 例如“优先更换某配件”
  - 例如“建议你直接去做 X”

### Risk Trigger Strategy

- 命中知识库回答链路，自动标记为 `rag_answer`
- 命中技术诊断关键词、结论词、建议词，标记为 `high_risk`
- 普通低风险解释性回答先直接放行

这样能保证第一版行为稳定、可解释、容易测试。

## Evidence Card Design

证据卡片不做成长引用堆砌，而是做成 3 层信息结构。

### Layer 1: Verdict Badge

直接展示当前答案的证据状态：

- `已证据支持`
- `部分支持`
- `证据不足，不确定`
- `证据冲突`
- `审查暂不可用`

### Layer 2: Evidence Summary

展示 1 到 3 条最相关证据片段，每条包含：

- 来源文档名
- 证据片段摘要
- 命中原因 / 相似度分数 / 排名
- 证据片段 id

### Layer 3: Uncertainty Reason

当答案被降级或冲突时，明确展示原因，例如：

- “知识库未找到直接支持该结论的片段”
- “现有证据只支持现象描述，不足以支持维修结论”
- “不同证据片段存在冲突”
- “审查链路暂时不可用，本次答案未完成事实核验”

## Review Agent Design

### Principle

审查 agent 不是第二个自由回答的大模型，而是一个受限裁判。  
它不负责重新回答用户问题，只负责判断候选答案是否被证据支持。

### Inputs

- 用户原始问题
- 主 agent 候选答案
- top-k 检索证据
- 风险标签
- 主 agent 声称引用的 evidence ids

### Outputs

审查结果必须是结构化输出：

- `verdict`: `supported | partial | unsupported | conflict`
- `confidence`: `high | medium | low`
- `reason`: 一句话说明判定原因
- `used_evidence_ids`: 真正支撑判断的证据 id 列表
- `rewrite_required`: 是否需要降级改写

### Review Rules

- 如果答案中的核心结论能被证据直接支持，输出 `supported`
- 如果只支持部分内容，输出 `partial`
- 如果没有直接证据支持结论，输出 `unsupported`
- 如果不同证据互相冲突，输出 `conflict`
- 如果主 agent 没有提供合法引用 id，默认视为 `unsupported`

## Candidate Answer Contract

主 agent 输出需要从当前“纯文本答案”扩展为“候选答案结构”。

候选输出建议包含：

- `answer`
- `answer_type`
- `risk_level`
- `used_knowledge`
- `claimed_evidence_ids`
- `raw_reasoning_summary`

这样下游审查链路才能基于结构化信息工作，而不是从自然语言里反向猜测。

## Integration with Existing Codebase

### Existing Components to Reuse

- `backend/app/services/agent_service.py`
  - 作为总链路入口，新增“审查后处理阶段”

- `backend/app/services/structured_output_service.py`
  - 扩展以支持候选答案结构与审查结果结构

- `backend/app/infrastructure/tools/local/knowledge_base.py`
  - 从简单问答结果升级为可返回证据片段

- `backend/app/services/stream_response_service.py`
  - 增加新型 PROCESS / ANSWER 附加内容的流式透出能力

- `front/agent_web_ui/src/views/ChatPage.vue`
  - 增加证据卡片渲染区

### Proposed Insertion Point

不要推翻原有 orchestrator，而是在现有 `MultiAgentService.process_task()` 中增加一个“答案验证后处理阶段”：

1. 主 agent 正常完成候选答案生成
2. 若回答命中 `rag_answer` 或 `high_risk`，进入 review 流程
3. review 输出 verdict
4. postprocess 根据 verdict 组装最终回答

这样是外挂式增强，改动相对集中，风险低于重构主 agent 流程。

## Degradation Strategy

本次设计采用“允许回答，但必须降级”的策略，而不是严格拦截。

### Supported

- 正常回答
- 展示证据卡片
- 不加不确定标签

### Partial

- 保留可支持部分
- 明确标记“不确定”
- 写出缺失支撑点
- 展示当前已有证据

### Unsupported

- 允许给出保守回答
- 必须以“不确定 / 当前缺乏直接依据”开头
- 给出证据不足原因

### Conflict

- 不输出强结论
- 明确说明证据冲突
- 建议进一步确认或人工处理

### Review Unavailable

- 不把系统错误误当成证据支持
- 输出“审查暂不可用”
- 仍可附上已检索证据卡片

## Failure Handling

验证失败不等于系统失败。

### Failure Cases

- 审查 agent 超时或调用失败
- 知识库检索为空
- 检索证据互相冲突
- 主 agent 未返回 evidence id
- 审查结果 JSON 解析失败

### Handling Policy

- `review agent` 失败：
  - 最终回答进入“未完成审查”状态
  - 证据卡片显示 `审查暂不可用`

- 检索为空：
  - 回答默认降级为不确定
  - 原因写为“未检索到直接证据”

- 证据冲突：
  - 输出冲突提示
  - 不允许强结论

- evidence id 缺失或非法：
  - 审查直接判 `unsupported`

这能避免新增审查链路后系统频繁因局部失败而中断。

## Metrics and Evaluation

第一版就应建立最小可用评测闭环。

### Core Metrics

- `evidence_coverage`
  - 最终回答中带证据卡片的比例

- `supported_answer_rate`
  - 被审查判为 `supported` 的比例

- `downgrade_rate`
  - 被降级为不确定回答的比例

- `hallucination_catch_rate`
  - 在自建测试集里，被识别并降级的无依据回答比例

### Evaluation Dataset

建立一套小型离线评测样本，覆盖：

- 有明确证据支撑
- 证据不足
- 证据冲突
- 模型容易编造的维修结论

这套评测集是后续写简历和答面试时最重要的支撑材料之一。

## Testing Strategy

### Unit Tests

- 风险分类规则测试
- 审查 verdict 到最终回答映射测试
- 不确定性改写逻辑测试
- 证据卡片组装测试

### Integration Tests

模拟以下链路：

- 知识库命中 + 审查支持
- 知识库命中 + 证据不足
- 知识库命中 + 证据冲突
- 审查 agent 失败

### UI Tests

- 前端证据卡片渲染
- verdict 状态标签显示
- 不确定原因展示

## Resume-Level Outcome

如果按本设计落地，项目可以从“多智能体 + 知识库问答”升级成“具备防幻觉治理能力的可解释问答系统”。

简历亮点可表述为：

- 设计并实现基于 RAG 的防幻觉回答链路，引入证据卡片与审查 Agent，对知识库问答和高风险诊断结论进行二次核验
- 构建证据支持 / 部分支持 / 证据不足的分级回答机制，在证据不足时自动降级为不确定回答并解释原因
- 建立结构化审查结果、前端证据可视化与离线评测闭环，提升回答可解释性与事实可靠性

## Scope Check

本设计聚焦于一个单独可实施的子系统：

- 证据检索与引用
- 审查 agent
- 降级回答
- 证据卡片
- 评测闭环

没有扩展到完整推荐系统、全量对话审核或复杂模型编排平台，因此适合作为单份 spec 对应一份 implementation plan。

## Ambiguity Resolution

以下边界已在本 spec 中明确：

- 不做严格拦截，采用“允许回答但必须降级”的策略
- 审查范围优先覆盖知识库回答与高风险结论，不做全量回答审查
- 审查 agent 只做核验，不重新生成答案
- 证据不足时必须展示原因，而不是简单返回“我不知道”
