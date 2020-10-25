CREATE TABLE guild_config (
  guild_id BIGINT NOT NULL PRIMARY KEY,
  prefix TEXT,
  member_log_channel_id BIGINT,
  message_log_channel_id BIGINT,
  moderator_log_channel_id BIGINT
);

INSERT INTO guild_config (guild_id)
SELECT guild_id
FROM message_metadata
UNION
SELECT guild_id
FROM member_history
UNION
SELECT guild_id
FROM moderator_action;

ALTER TABLE message_metadata
ADD FOREIGN KEY (guild_id) REFERENCES guild_config (guild_id);

ALTER TABLE member_history
ADD FOREIGN KEY (guild_id) REFERENCES guild_config (guild_id);

ALTER TABLE moderator_action
ADD FOREIGN KEY (guild_id) REFERENCES guild_config (guild_id);
