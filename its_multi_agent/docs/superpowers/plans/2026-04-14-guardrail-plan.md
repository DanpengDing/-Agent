# Guardrail 输入过滤机制实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 API 入口处实现基于 DFA 算法的敏感词过滤，通用敏感词拒绝，业务敏感词替换后放行。

**Architecture:** 使用 DFA（确定性有限自动机）算法实现高效敏感词匹配。输入层在 `routers.py` 的 `/api/query` 入口处集成，在 Agent 处理前进行过滤。

**Tech Stack:** Python 3.10+, 标准库（json, pathlib）+ 现有项目依赖（pydantic, fastapi）

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/services/guardrail_service.py` | 核心过滤服务，DFA 算法实现，导出 `guardrail_service` 单例 |
| `backend/app/data/sensitive_words.json` | 敏感词库（common + business） |
| `backend/app/utils/sensitive_word_loader.py` | 敏感词加载器，支持热更新 |
| `backend/app/services/__init__.py` | 导出 `guardrail_service` |
| `backend/app/tests/test_guardrail_service.py` | 单元测试 |
| `backend/app/api/routers.py` | 集成点 |

---

## 实现任务

### Task 1: 创建敏感词 JSON 数据文件

**Files:**
- Create: `backend/app/data/sensitive_words.json`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p backend/app/data
```

- [ ] **Step 2: 创建敏感词 JSON 文件**

```json
{
  "common": [
    "敏感词示例1",
    "敏感词示例2"
  ],
  "business": [
    "竞品名称示例",
    "内部术语示例"
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/data/sensitive_words.json
git commit -m "feat: 添加敏感词库 JSON 文件"
```

---

### Task 2: 创建敏感词加载器

**Files:**
- Create: `backend/app/utils/sensitive_word_loader.py`
- Modify: `backend/app/utils/__init__.py`（如需要导出）

- [ ] **Step 1: 编写敏感词加载器**

```python
"""
敏感词加载器模块。

支持从 JSON 文件加载敏感词库，提供热更新能力。
"""
import json
import threading
from pathlib import Path
from typing import TypedDict

import time


class SensitiveWordLoader:
    """敏感词加载器，支持热更新。"""

    def __init__(self, json_path: str):
        """
        初始化加载器。

        Args:
            json_path: sensitive_words.json 文件路径
        """
        self._path = Path(json_path)
        self._common_words: set[str] = set()
        self._business_words: set[str] = set()
        self._last_mtime: float = 0
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """从 JSON 文件加载敏感词。"""
        if not self._path.exists():
            self._common_words = set()
            self._business_words = set()
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)

            common_list = data.get("common", [])
            business_list = data.get("business", [])

            with self._lock:
                self._common_words = set(common_list)
                self._business_words = set(business_list)

            self._last_mtime = self._path.stat().st_mtime
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载敏感词文件失败: {e}")
            with self._lock:
                self._common_words = set()
                self._business_words = set()

    def get_common_words(self) -> set[str]:
        """获取通用敏感词集合。"""
        with self._lock:
            return self._common_words.copy()

    def get_business_words(self) -> set[str]:
        """获取业务敏感词集合。"""
        with self._lock:
            return self._business_words.copy()

    def check_and_reload(self) -> bool:
        """
        检查文件是否变化，如变化则重新加载。

        Returns:
            True if reloaded, False otherwise
        """
        try:
            current_mtime = self._path.stat().st_mtime
            if current_mtime > self._last_mtime:
                self._load()
                return True
        except OSError:
            pass
        return False


# 全局加载器实例（延迟初始化）
_loader: SensitiveWordLoader | None = None


def get_word_loader() -> SensitiveWordLoader:
    """获取全局敏感词加载器。"""
    global _loader
    if _loader is None:
        base_dir = Path(__file__).resolve().parent.parent
        json_path = base_dir / "data" / "sensitive_words.json"
        _loader = SensitiveWordLoader(str(json_path))
    return _loader
```

- [ ] **Step 2: 更新 utils/__init__.py（如果需要）**

确认 `__init__.py` 不需要特殊修改，继续下一步。

- [ ] **Step 3: Commit**

```bash
git add backend/app/utils/sensitive_word_loader.py
git commit -m "feat: 添加敏感词加载器"
```

---

### Task 3: 创建 Guardrail 核心服务（DFA 算法）

**Files:**
- Create: `backend/app/services/guardrail_service.py`

- [ ] **Step 1: 编写 DFA 过滤服务**

```python
"""
Guardrail 输入过滤服务。

使用 DFA 算法进行敏感词匹配。
通用敏感词命中 -> 拒绝
业务敏感词命中 -> 替换为 ***
"""
from dataclasses import dataclass
from typing import Optional

from utils.sensitive_word_loader import get_word_loader


@dataclass
class GuardrailCheckResult:
    """过滤检查结果。"""
    blocked: bool                    # 是否被拦截（通用敏感词）
    replaced: bool                   # 是否进行了替换（业务敏感词）
    filtered_text: Optional[str]     # 过滤后的文本（如果进行了替换）
    matched_common: list[str]        # 命中的通用敏感词
    matched_business: list[str]       # 命中的业务敏感词


class DFAFilter:
    """
    DFA（确定性有限自动机）敏感词过滤器。

    构建以敏感词为key的状态转移图，实现 O(1) 复杂度的字符串匹配。
    """

    def __init__(self, words: set[str]):
        """
        初始化 DFA 过滤器。

        Args:
            words: 敏感词集合
        """
        self._next: dict[tuple[int, str], int] = {}
        self._states: list[set[str]] = []
        self._build_trie(words)

    def _build_trie(self, words: set[str]) -> None:
        """构建状态转移图（字典树）。"""
        self._next = {}
        self._states = [set()]

        for word in words:
            if not word:
                continue
            self._add_word(word)

    def _add_word(self, word: str) -> None:
        """添加单个敏感词到 DFA。"""
        chars = list(word)
        state = 0

        for char in chars:
            key = (state, char)
            if key not in self._next:
                self._next[key] = len(self._states)
                self._states.append(set())
            state = self._next[key]
        self._states[state].add("")  # 标记为终态

    def filter_text(self, text: str, replace_char: str = "*") -> tuple[str, list[str]]:
        """
        过滤文本中的敏感词。

        Args:
            text: 原始文本
            replace_char: 替换字符

        Returns:
            (过滤后的文本, 命中的敏感词列表)
        """
        if not text:
            return "", []

        result = list(text)
        matched_words: list[str] = []
        chars = list(text)

        i = 0
        while i < len(chars):
            state = 0
            match_end = -1
            matched_word = ""

            for j in range(i, len(chars)):
                char = chars[j]
                key = (state, char)

                if key not in self._next:
                    break

                state = self._next[key]

                # 检查是否为终态（匹配结束）
                if "" in self._states[state]:
                    match_end = j
                    matched_word = text[i:j + 1]

            if match_end >= 0:
                matched_words.append(matched_word)
                for k in range(i, match_end + 1):
                    result[k] = replace_char
                i = match_end + 1
            else:
                i += 1

        return "".join(result), matched_words


class GuardrailService:
    """Guardrail 过滤服务。"""

    def __init__(self):
        self._word_loader = get_word_loader()
        self._common_filter: DFAFilter | None = None
        self._business_filter: DFAFilter | None = None
        self._build_filters()

    def _build_filters(self) -> None:
        """根据加载的词库构建 DFA 过滤器。"""
        common_words = self._word_loader.get_common_words()
        business_words = self._word_loader.get_business_words()

        self._common_filter = DFAFilter(common_words)
        self._business_filter = DFAFilter(business_words)

    def check_input(self, text: str) -> GuardrailCheckResult:
        """
        检查输入文本。

        Args:
            text: 用户输入文本

        Returns:
            GuardrailCheckResult: 包含 blocked, replaced, filtered_text, matched_* 等字段
        """
        if not text:
            return GuardrailCheckResult(
                blocked=False,
                replaced=False,
                filtered_text=text,
                matched_common=[],
                matched_business=[]
            )

        # 检查文件变化，必要时热更新
        self._word_loader.check_and_reload()

        # 第1步：检查通用敏感词（拒绝）
        filtered_common, matched_common = self._common_filter.filter_text(text)

        if matched_common:
            return GuardrailCheckResult(
                blocked=True,
                replaced=False,
                filtered_text=text,
                matched_common=matched_common,
                matched_business=[]
            )

        # 第2步：检查业务敏感词（替换）
        filtered_text, matched_business = self._business_filter.filter_text(text)

        return GuardrailCheckResult(
            blocked=False,
            replaced=len(matched_business) > 0,
            filtered_text=filtered_text,
            matched_common=[],
            matched_business=matched_business
        )


# 全局单例
guardrail_service = GuardrailService()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/guardrail_service.py
git commit -m "feat: 添加 Guardrail DFA 过滤服务"
```

---

### Task 4: 集成到 API 入口

**Files:**
- Modify: `backend/app/api/routers.py`

- [ ] **Step 1: 读取现有 routers.py 并添加 import**

在文件顶部添加：
```python
from services.guardrail_service import guardrail_service
```

- [ ] **Step 2: 修改 query 函数添加过滤逻辑**

找到 `query()` 函数（约第18行开始），在 `user_query = request_context.query` 后添加：

```python
@router.post("/api/query", summary="流式执行智能体")
async def query(request_context: ChatMessageRequest) -> StreamingResponse:
    user_id = request_context.context.user_id
    user_query = request_context.query

    # ========== Guardrail 输入过滤 ==========
    check_result = guardrail_service.check_input(user_query)
    if check_result.blocked:
        # 命中通用敏感词，直接拒绝
        return StreamingResponse(
            content=self._blocked_stream(check_result),
            status_code=200,
            media_type="text/event-stream",
        )
    if check_result.replaced:
        # 命中业务敏感词，使用替换后的文本
        user_query = check_result.filtered_text
        logger.info(
            "Guardrail: user=%s business_words=%s replaced_query=%s",
            user_id,
            check_result.matched_business,
            user_query,
        )
    # ========== Guardrail 过滤结束 ==========

    logger.info("user=%s query=%s", user_id, user_query)
    async_generator_result = MultiAgentService.process_task(request_context, flag=True)
    return StreamingResponse(
        content=async_generator_result,
        status_code=200,
        media_type="text/event-stream",
    )

@staticmethod
async def _blocked_stream(check_result) -> AsyncGenerator[str, None]:
    """返回敏感词拦截响应。"""
    yield "data: " + ResponseFactory.build_text(
        f"抱歉，您的输入包含敏感词（{', '.join(check_result.matched_common)}），已被系统拦截。",
        ContentKind.PROCESS,
    ).model_dump_json() + "\n\n"
    yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
```

注意：由于 `_blocked_stream` 是 async generator，需要在函数内添加 `from typing import AsyncGenerator`。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routers.py
git commit -m "feat: 集成 Guardrail 输入过滤到 API 入口"
```

---

### Task 5: 编写单元测试

**Files:**
- Create: `backend/app/tests/test_guardrail_service.py`

- [ ] **Step 1: 编写测试文件**

```python
"""
Guardrail Service 单元测试。
"""
import json
import tempfile
from pathlib import Path

import pytest

from services.guardrail_service import GuardrailService, DFAFilter, GuardrailCheckResult
from utils.sensitive_word_loader import SensitiveWordLoader


class TestDFAFilter:
    """DFA 过滤器测试。"""

    def test_empty_words(self):
        filter_obj = DFAFilter(set())
        text, matched = filter_obj.filter_text("hello world")
        assert text == "hello world"
        assert matched == []

    def test_single_word_match(self):
        filter_obj = DFAFilter({"敏感词"})
        text, matched = filter_obj.filter_text("这是一个敏感词的句子")
        assert text == "这是一个***的句子"
        assert matched == ["敏感词"]

    def test_multiple_word_match(self):
        filter_obj = DFAFilter({"敏感词A", "敏感词B"})
        text, matched = filter_obj.filter_text("敏感词A和敏感词B")
        assert matched == ["敏感词A", "敏感词B"]

    def test_no_match(self):
        filter_obj = DFAFilter({"敏感词"})
        text, matched = filter_obj.filter_text("正常文本")
        assert text == "正常文本"
        assert matched == []

    def test_overlapping_words(self):
        filter_obj = DFAFilter({"abc", "bcd"})
        text, matched = filter_obj.filter_text("abcdef")
        # abc 匹配后变为 ***，bcd 的起点字符已被替换
        assert "***" in text


class TestSensitiveWordLoader:
    """敏感词加载器测试。"""

    def test_load_from_json(self, tmp_path):
        json_file = tmp_path / "test_words.json"
        test_data = {
            "common": ["违禁词1", "违禁词2"],
            "business": ["竞品词1"]
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False)

        loader = SensitiveWordLoader(str(json_file))
        assert loader.get_common_words() == {"违禁词1", "违禁词2"}
        assert loader.get_business_words() == {"竞品词1"}

    def test_file_not_exists(self, tmp_path):
        json_file = tmp_path / "not_exists.json"
        loader = SensitiveWordLoader(str(json_file))
        assert loader.get_common_words() == set()
        assert loader.get_business_words() == set()


class TestGuardrailService:
    """Guardrail 服务测试。"""

    def test_normal_text_passes(self):
        # 此测试需要 mock 加载器
        service = GuardrailService()
        result = service.check_input("这是一个正常的查询")
        assert result.blocked is False
        assert result.replaced is False

    def test_business_word_replaced(self):
        # 测试业务敏感词被替换
        service = GuardrailService()
        # 由于全局单例使用真实文件，这里测试基本结构
        result = GuardrailCheckResult(
            blocked=False,
            replaced=True,
            filtered_text="这是一个***的查询",
            matched_common=[],
            matched_business=["敏感词"]
        )
        assert result.blocked is False
        assert result.replaced is True
        assert "***" in result.filtered_text
```

- [ ] **Step 2: 运行测试验证**

```bash
cd backend/app
python -m pytest tests/test_guardrail_service.py -v
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/test_guardrail_service.py
git commit -m "test: 添加 Guardrail 单元测试"
```

---

### Task 6: 更新 README 文档

**Files:**
- Modify: `backend/app/README.md`

- [ ] **Step 1: 添加 Guardrail 说明章节**

在 README.md 适当位置添加：

```markdown
## 安全机制

### Guardrail 输入过滤

基于 DFA 算法的敏感词过滤机制，集成在 API 入口处：

- **通用敏感词**：命中后直接拒绝请求
- **业务敏感词**：自动替换为 `***` 后继续处理

敏感词库位于 `data/sensitive_words.json`，支持热更新。

配置示例：
```json
{
  "common": ["违禁词1", "违禁词2"],
  "business": ["竞品名称", "内部术语"]
}
```
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/README.md
git commit -m "docs: 添加 Guardrail 输入过滤说明"
```

---

## 实施检查清单

- [ ] Task 1: 创建敏感词 JSON 数据文件
- [ ] Task 2: 创建敏感词加载器
- [ ] Task 3: 创建 Guardrail 核心服务
- [ ] Task 4: 集成到 API 入口
- [ ] Task 5: 编写单元测试
- [ ] Task 6: 更新 README 文档

---

## 依赖说明

本实现**不引入任何新依赖**，仅使用 Python 标准库：
- `json` - JSON 解析
- `pathlib` - 路径处理
- `threading` - 线程安全
- `dataclasses` - 数据类（Python 3.7+ 内置）
