CREATE TYPE moderator_action_type AS ENUM (
  'ban',
  'unban',
  'kick',
  'silence',
  'unsilence',
  'warn'
);

CREATE TABLE moderator_action (
  action_id SERIAL NOT NULL PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  target_id BIGINT NOT NULL,
  moderator_id BIGINT NOT NULL,
  action_type moderator_action_type NOT NULL,
  recorded_at TIMESTAMP NOT NULL,
  duration INT,
  reason TEXT
);
