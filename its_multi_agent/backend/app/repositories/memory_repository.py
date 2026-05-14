from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pymysql.cursors import DictCursor

from infrastructure.database.database_pool import pool
from infrastructure.logging.logger import logger


class MemoryRepository:
    """长期记忆与用户偏好的 MySQL 仓储。"""

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
                CREATE TABLE IF NOT EXISTS user_long_term_memory (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    user_id VARCHAR(128) NOT NULL,
                    memory_key VARCHAR(128) NOT NULL,
                    memory_value TEXT NOT NULL,
                    memory_type VARCHAR(64) NOT NULL DEFAULT 'fact',
                    topic VARCHAR(128) NOT NULL DEFAULT '',
                    confidence DECIMAL(4,2) NOT NULL DEFAULT 0.80,
                    source_session_id VARCHAR(255) DEFAULT '',
                    source_text TEXT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    expires_at DATETIME NULL,
                    metadata_json JSON NULL,
                    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_user_memory_key (user_id, memory_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    user_id VARCHAR(128) NOT NULL,
                    preference_key VARCHAR(128) NOT NULL,
                    preference_value TEXT NOT NULL,
                    preference_type VARCHAR(64) NOT NULL DEFAULT 'explicit',
                    confidence DECIMAL(4,2) NOT NULL DEFAULT 0.80,
                    source_session_id VARCHAR(255) DEFAULT '',
                    source_text TEXT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    metadata_json JSON NULL,
                    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_user_preference_key (user_id, preference_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            self._ensure_table_columns(cursor)
            connection.commit()
            self._initialized = True
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def upsert_long_term_memory(
        self,
        user_id: str,
        memory_key: str,
        memory_value: str,
        memory_type: str = "fact",
        topic: str = "",
        confidence: float = 0.80,
        source_session_id: str = "",
        source_text: str = "",
        expires_at: Optional[datetime] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        self.ensure_tables()
        self._upsert_record(
            table_name="user_long_term_memory",
            key_column="memory_key",
            value_column="memory_value",
            user_id=user_id,
            key=memory_key,
            value=memory_value,
            record_type=memory_type,
            topic=topic,
            confidence=confidence,
            source_session_id=source_session_id,
            source_text=source_text,
            expires_at=expires_at,
            metadata_json=metadata_json,
        )

    def upsert_user_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: str,
        preference_type: str = "explicit",
        confidence: float = 0.80,
        source_session_id: str = "",
        source_text: str = "",
        metadata_json: Optional[str] = None,
    ) -> None:
        self.ensure_tables()
        self._upsert_record(
            table_name="user_preferences",
            key_column="preference_key",
            value_column="preference_value",
            user_id=user_id,
            key=preference_key,
            value=preference_value,
            record_type=preference_type,
            topic="",
            confidence=confidence,
            source_session_id=source_session_id,
            source_text=source_text,
            expires_at=None,
            metadata_json=metadata_json,
        )

    def list_long_term_memories(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.ensure_tables()
        return self._list_records(
            table_name="user_long_term_memory",
            key_column="memory_key",
            value_column="memory_value",
            type_column="memory_type",
            user_id=user_id,
            limit=limit,
        )

    def list_user_preferences(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        self.ensure_tables()
        return self._list_records(
            table_name="user_preferences",
            key_column="preference_key",
            value_column="preference_value",
            type_column="preference_type",
            user_id=user_id,
            limit=limit,
        )

    def delete_user_preference(self, user_id: str, preference_key: str) -> int:
        self.ensure_tables()
        return self._soft_delete_record("user_preferences", "preference_key", user_id, preference_key)

    def _upsert_record(
        self,
        table_name: str,
        key_column: str,
        value_column: str,
        user_id: str,
        key: str,
        value: str,
        record_type: str,
        topic: str,
        confidence: float,
        source_session_id: str,
        source_text: str,
        expires_at: Optional[datetime],
        metadata_json: Optional[str],
    ) -> None:
        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor()
            if table_name == "user_long_term_memory":
                cursor.execute(
                    f"""
                    INSERT INTO {table_name}
                        (user_id, {key_column}, {value_column}, memory_type, topic, confidence, source_session_id, source_text, status, expires_at, metadata_json, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        {value_column}=VALUES({value_column}),
                        memory_type=VALUES(memory_type),
                        topic=VALUES(topic),
                        confidence=VALUES(confidence),
                        source_session_id=VALUES(source_session_id),
                        source_text=VALUES(source_text),
                        status='active',
                        expires_at=VALUES(expires_at),
                        metadata_json=VALUES(metadata_json),
                        last_seen_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (user_id, key, value, record_type, topic, confidence, source_session_id, source_text, expires_at, metadata_json),
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO {table_name}
                        (user_id, {key_column}, {value_column}, preference_type, confidence, source_session_id, source_text, status, metadata_json, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        {value_column}=VALUES({value_column}),
                        preference_type=VALUES(preference_type),
                        confidence=VALUES(confidence),
                        source_session_id=VALUES(source_session_id),
                        source_text=VALUES(source_text),
                        status='active',
                        metadata_json=VALUES(metadata_json),
                        last_seen_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (user_id, key, value, record_type, confidence, source_session_id, source_text, metadata_json),
                )
            connection.commit()
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _list_records(
        self,
        table_name: str,
        key_column: str,
        value_column: str,
        type_column: str,
        user_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor(DictCursor)
            cursor.execute(
                f"""
                SELECT
                    {key_column} AS memory_key,
                    {value_column} AS memory_value,
                    {type_column} AS memory_type,
                    confidence,
                    source_session_id,
                    source_text,
                    metadata_json,
                    last_seen_at,
                    updated_at
                FROM {table_name}
                WHERE user_id=%s
                  AND status='active'
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return list(cursor.fetchall() or [])
        except Exception as exc:
            logger.error("[MemoryRepository] list records failed table=%s user=%s error=%s", table_name, user_id, exc)
            return []
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _soft_delete_record(self, table_name: str, key_column: str, user_id: str, key: str) -> int:
        connection = None
        cursor = None
        try:
            connection = pool.connection()
            cursor = connection.cursor()
            affected = cursor.execute(
                f"""
                UPDATE {table_name}
                SET status='deleted', updated_at=CURRENT_TIMESTAMP
                WHERE user_id=%s AND {key_column}=%s AND status='active'
                """,
                (user_id, key),
            )
            connection.commit()
            return int(affected or 0)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _ensure_table_columns(self, cursor) -> None:
        required_columns = {
            "user_long_term_memory": {
                "memory_type": "ALTER TABLE user_long_term_memory ADD COLUMN memory_type VARCHAR(64) NOT NULL DEFAULT 'fact' AFTER memory_value",
                "topic": "ALTER TABLE user_long_term_memory ADD COLUMN topic VARCHAR(128) NOT NULL DEFAULT '' AFTER memory_type",
                "source_text": "ALTER TABLE user_long_term_memory ADD COLUMN source_text TEXT NULL AFTER source_session_id",
                "metadata_json": "ALTER TABLE user_long_term_memory ADD COLUMN metadata_json JSON NULL AFTER expires_at",
                "last_seen_at": "ALTER TABLE user_long_term_memory ADD COLUMN last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER metadata_json",
            },
            "user_preferences": {
                "preference_type": "ALTER TABLE user_preferences ADD COLUMN preference_type VARCHAR(64) NOT NULL DEFAULT 'explicit' AFTER preference_value",
                "source_text": "ALTER TABLE user_preferences ADD COLUMN source_text TEXT NULL AFTER source_session_id",
                "metadata_json": "ALTER TABLE user_preferences ADD COLUMN metadata_json JSON NULL AFTER status",
                "last_seen_at": "ALTER TABLE user_preferences ADD COLUMN last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER metadata_json",
            },
        }

        for table_name, columns in required_columns.items():
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            existing_columns = {row[0] for row in cursor.fetchall()}
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    logger.info("[MemoryRepository] upgrading table=%s add_column=%s", table_name, column_name)
                    cursor.execute(ddl)


memory_repository = MemoryRepository()
