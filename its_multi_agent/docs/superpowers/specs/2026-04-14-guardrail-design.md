# Guardrail 输入过滤机制设计

## 1. 概述

在 `routers.py` 的 `/api/query` 入口处，集成基于 DFA 算法的敏感词过滤服务。通用敏感词直接拒绝，业务敏感词替换后放行。

## 2. 核心组件

| 文件路径 | 说明 |
|----------|------|
| `backend/app/services/guardrail_service.py` | 核心过滤服务，DFA 算法实现 |
| `backend/app/data/sensitive_words.json` | 敏感词库（通用 + 业务定制） |
| `backend/app/utils/sensitive_word_loader.py` | 敏感词加载器，支持热更新 |

## 3. 敏感词库格式

```json
{
  "common": ["敏感词A", "敏感词B"],
  "business": ["竞品名称", "内部术语"]
}
```

- `common`: 通用敏感词，命中后**直接拒绝**
- `business`: 业务敏感词，命中后**替换为 *** 后放行**

## 4. DFA 算法

- 使用 Deterministic Finite Automaton (DFA) 算法
- 时间复杂度 O(1) 对于任意长度的文本
- 预处理构建状态转移图，查询高效

## 5. 过滤动作

| 命中类型 | 动作 | 返回内容 |
|----------|------|----------|
| 通用敏感词 | 拒绝 | `{"success": false, "error": "输入包含敏感词，已被拦截"}` |
| 业务敏感词 | 替换放行 | 使用替换后的文本继续处理 |

## 6. 集成点

在 `api/routers.py` 的 `query()` 函数中：

```python
# 第1步：敏感词检查
check_result = guardrail_service.check_input(user_query)
if check_result.blocked:
    return {"success": False, "error": "输入包含敏感词，已被拦截"}
if check_result.replaced:
    user_query = check_result.filtered_text  # 使用替换后的文本

# 第2步：继续原有流程...
```

## 7. 热更新支持

`sensitive_word_loader.py` 监听 JSON 文件变化，自动重新加载词库，无需重启服务。

## 8. 测试覆盖

- 单元测试：`backend/app/tests/test_guardrail_service.py`
- 测试场景：
  - 通用敏感词命中 → 拒绝
  - 业务敏感词命中 → 替换
  - 正常文本 → 放行
  - 多词匹配 → 全部处理
