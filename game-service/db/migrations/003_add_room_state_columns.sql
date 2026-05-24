-- Migration: Add moves_json and metadata columns to rooms table
-- Required for game state persistence (server restart recovery / reconnect)

ALTER TABLE rooms ADD COLUMN IF NOT EXISTS moves_json JSONB;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS metadata JSONB;

COMMENT ON COLUMN rooms.moves_json IS '着法历史 (JSON 数组)';
COMMENT ON COLUMN rooms.metadata IS '游戏状态元数据 (current_player, timer, etc.)';
