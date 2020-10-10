CREATE TABLE message_metadata (
  message_id BIGINT NOT NULL PRIMARY KEY,
  channel_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  author_id BIGINT NOT NULL
);
