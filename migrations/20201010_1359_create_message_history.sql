CREATE TABLE message_history (
  message_id BIGINT NOT NULL REFERENCES message_metadata (message_id),
  version_at TIMESTAMP NOT NULL,
  content TEXT,
  PRIMARY KEY (message_id, version_at)
);
