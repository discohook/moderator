CREATE TABLE message_history (
  message_id BIGINT NOT NULL REFERENCES message_metadata (message_id),
  when_is_it TIMESTAMP NOT NULL,
  content TEXT,
  PRIMARY KEY (message_id, when_is_it)
);
