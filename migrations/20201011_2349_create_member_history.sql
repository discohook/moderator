CREATE TABLE member_history (
  guild_id BIGINT NOT NULL,
  member_id BIGINT NOT NULL,
  version_at TIMESTAMP NOT NULL,
  tag TEXT,
  nick TEXT,
  PRIMARY KEY (guild_id, member_id, version_at)
);
