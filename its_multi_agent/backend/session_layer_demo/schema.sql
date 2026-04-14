CREATE TABLE chat_session (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '新会话',
    summary TEXT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    KEY idx_user_updated (user_id, updated_at)
);

CREATE TABLE chat_message (
    message_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    sequence_num INT NOT NULL,
    token_count INT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_chat_message_session
        FOREIGN KEY (session_id) REFERENCES chat_session(session_id),
    UNIQUE KEY uk_session_sequence (session_id, sequence_num),
    KEY idx_session_created (session_id, created_at)
);

CREATE TABLE chat_event_log (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_payload JSON NOT NULL,
    created_at DATETIME NOT NULL,
    KEY idx_session_event_time (session_id, created_at)
);
