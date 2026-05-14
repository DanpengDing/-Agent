from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymysql.cursors import DictCursor

from infrastructure.database.database_pool import pool
from infrastructure.logging.logger import logger


class TaskMemoryRepository:
    """任务状态记忆持久化仓储。"""

    ACTIVE_STATUSES = ("active", "waiting_approval", "blocked", "retrying")

    def __init__(self) -> None:
        self._initialized = False

    def ensure_tables(self) -> None:
        if self._initialized:
            return

        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_task_memory (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    user_id VARCHAR(128) NOT NULL,
                    session_id VARCHAR(255) NOT NULL DEFAULT '',
                    task_id VARCHAR(64) NOT NULL,
                    task_type VARCHAR(64) NOT NULL,
                    task_goal TEXT NOT NULL,
                    task_status VARCHAR(32) NOT NULL DEFAULT 'active',
                    task_stage VARCHAR(64) NOT NULL DEFAULT 'intent_routed',
                    task_summary TEXT NULL,
                    structured_context_json JSON NULL,
                    last_tool_name VARCHAR(128) NULL,
                    last_tool_result_json JSON NULL,
                    last_error TEXT NULL,
                    waiting_approval_token VARCHAR(128) NULL,
                    retry_count INT NOT NULL DEFAULT 0,
                    priority INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    last_active_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at DATETIME NULL,
                    UNIQUE KEY uniq_task_id (task_id),
                    KEY idx_user_session_status (user_id, session_id, task_status, updated_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            connection.commit()
            self._initialized = True
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def create_task(
        self,
        user_id: str,
        session_id: str,
        task_type: str,
        task_goal: str,
        task_status: str = "active",
        task_stage: str = "intent_routed",
        task_summary: str = "",
        structured_context: Optional[Dict[str, Any]] = None,
        priority: int = 0,
    ) -> Dict[str, Any]:
        self.ensure_tables()
        task_id = str(uuid.uuid4())
        record = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": session_id or "",
            "task_type": task_type,
            "task_goal": task_goal,
            "task_status": task_status,
            "task_stage": task_stage,
            "task_summary": task_summary or task_goal,
            "structured_context_json": self._serialize_json(structured_context),
            "last_tool_name": None,
            "last_tool_result_json": None,
            "last_error": None,
            "waiting_approval_token": None,
            "retry_count": 0,
            "priority": priority,
        }

        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO user_task_memory (
                    user_id, session_id, task_id, task_type, task_goal, task_status, task_stage,
                    task_summary, structured_context_json, last_tool_name, last_tool_result_json,
                    last_error, waiting_approval_token, retry_count, priority, last_active_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (
                    record["user_id"],
                    record["session_id"],
                    record["task_id"],
                    record["task_type"],
                    record["task_goal"],
                    record["task_status"],
                    record["task_stage"],
                    record["task_summary"],
                    record["structured_context_json"],
                    record["last_tool_name"],
                    record["last_tool_result_json"],
                    record["last_error"],
                    record["waiting_approval_token"],
                    record["retry_count"],
                    record["priority"],
                ),
            )
            connection.commit()
            return self.get_task_by_id(user_id=user_id, task_id=task_id) or self._normalize_record(record)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def update_task(self, user_id: str, task_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if not fields:
            return self.get_task_by_id(user_id, task_id)

        normalized = self._normalize_update_fields(fields)
        set_clauses = [f"{column}=%s" for column in normalized]
        values = list(normalized.values())
        values.extend([user_id, task_id])

        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor()
            cursor.execute(
                f"""
                UPDATE user_task_memory
                SET {", ".join(set_clauses)}, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=%s AND task_id=%s
                """,
                values,
            )
            connection.commit()
            return self.get_task_by_id(user_id=user_id, task_id=task_id)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def get_task_by_id(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        rows = self._query_rows(
            """
            SELECT * FROM user_task_memory
            WHERE user_id=%s AND task_id=%s
            LIMIT 1
            """,
            (user_id, task_id),
        )
        return rows[0] if rows else None

    def get_active_task(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        rows = self._query_rows(
            f"""
            SELECT * FROM user_task_memory
            WHERE user_id=%s
              AND session_id=%s
              AND task_status IN ({",".join(["%s"] * len(self.ACTIVE_STATUSES))})
            ORDER BY
              CASE task_status
                WHEN 'waiting_approval' THEN 0
                WHEN 'retrying' THEN 1
                WHEN 'blocked' THEN 2
                ELSE 3
              END,
              last_active_at DESC,
              updated_at DESC
            LIMIT 1
            """,
            (user_id, session_id or "", *self.ACTIVE_STATUSES),
        )
        return rows[0] if rows else None

    def get_task_by_approval_token(self, user_id: str, session_id: str, token: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        rows = self._query_rows(
            """
            SELECT * FROM user_task_memory
            WHERE user_id=%s
              AND session_id=%s
              AND waiting_approval_token=%s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, session_id or "", token),
        )
        return rows[0] if rows else None

    def list_tasks(self, user_id: str, session_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if session_id:
            return self._query_rows(
                """
                SELECT * FROM user_task_memory
                WHERE user_id=%s AND session_id=%s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_id, session_id, limit),
            )
        return self._query_rows(
            """
            SELECT * FROM user_task_memory
            WHERE user_id=%s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )

    def _query_rows(self, sql: str, params: tuple[Any, ...]) -> List[Dict[str, Any]]:
        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor(DictCursor)
            cursor.execute(sql, params)
            rows = cursor.fetchall() or []
            return [self._normalize_record(row) for row in rows]
        except Exception as exc:
            logger.error("[TaskMemoryRepository] query failed error=%s", exc)
            return []
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def _serialize_json(value: Optional[Dict[str, Any]]) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _deserialize_json(value: Any) -> Optional[Dict[str, Any]]:
        if value in (None, "", b""):
            return None
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except Exception:
            return {"raw": str(value)}

    def _normalize_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(row)
        normalized["structured_context_json"] = self._deserialize_json(normalized.get("structured_context_json"))
        normalized["last_tool_result_json"] = self._deserialize_json(normalized.get("last_tool_result_json"))
        return normalized

    def _normalize_update_fields(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(fields)
        if "structured_context_json" in normalized and isinstance(normalized["structured_context_json"], dict):
            normalized["structured_context_json"] = self._serialize_json(normalized["structured_context_json"])
        if "last_tool_result_json" in normalized and isinstance(normalized["last_tool_result_json"], dict):
            normalized["last_tool_result_json"] = self._serialize_json(normalized["last_tool_result_json"])
        if normalized.get("task_status") in {"completed", "cancelled"} and "closed_at" not in normalized:
            normalized["closed_at"] = datetime.now()
        return normalized


task_memory_repository = TaskMemoryRepository()
