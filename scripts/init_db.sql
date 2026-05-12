-- =========================================
-- 中国象棋对战游戏 - 数据库初始化脚本
-- Database: PostgreSQL 14+
-- =========================================

-- 创建数据库 (需要在 postgres 数据库中执行)
-- CREATE DATABASE xiangqi;

-- =========================================
-- 1. 用户表 (users)
-- =========================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE,
    nickname        VARCHAR(50),
    avatar_url      VARCHAR(500),
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT username_length CHECK (LENGTH(username) >= 3),
    CONSTRAINT username_charset CHECK (username ~ '^[a-zA-Z0-9_]+$')
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- =========================================
-- 2. ELO 积分表 (elo_ratings)
-- =========================================
CREATE TABLE IF NOT EXISTS elo_ratings (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    rating        INTEGER DEFAULT 1500,          -- ELO 积分，默认 1500
    games_count   INTEGER DEFAULT 0,              -- 总对局数
    wins_count    INTEGER DEFAULT 0,              -- 胜利次数
    losses_count  INTEGER DEFAULT 0,              -- 失败次数
    draws_count   INTEGER DEFAULT 0,              -- 和棋次数
    highest_rating INTEGER DEFAULT 1500,           -- 历史最高分
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT rating_range CHECK (rating >= 0 AND rating <= 4000),
    CONSTRAINT games_positive CHECK (games_count >= 0)
);

CREATE INDEX idx_elo_ratings_user_id ON elo_ratings(user_id);
CREATE INDEX idx_elo_ratings_rating ON elo_ratings(rating DESC);

-- =========================================
-- 3. 房间表 (rooms)
-- =========================================
CREATE TYPE room_type_t AS ENUM ('pvp', 'pve');
CREATE TYPE room_status_t AS ENUM ('waiting', 'ready', 'playing', 'finished');

CREATE TABLE IF NOT EXISTS rooms (
    id              VARCHAR(36) PRIMARY KEY,      -- UUID
    type            room_type_t NOT NULL,
    status          room_status_t DEFAULT 'waiting',
    
    -- 玩家信息
    red_player_id   BIGINT REFERENCES users(id),  -- 红方玩家
    black_player_id BIGINT REFERENCES users(id),  -- 黑方玩家 (PvE 时为 NULL)
    
    -- AI 相关信息 (PvE 时使用)
    ai_difficulty   INTEGER,                       -- AI 难度 1-5
    
    -- 游戏配置
    initial_time    INTEGER DEFAULT 600,           -- 初始时间(秒)
    increment       INTEGER DEFAULT 10,            -- 每步增加时间(秒)
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP WITH TIME ZONE,      -- 对局开始时间
    finished_at     TIMESTAMP WITH TIME ZONE,      -- 对局结束时间
    
    -- 游戏结果
    winner          INTEGER,                       -- 0=红方, 1=黑方, -1=无
    result          VARCHAR(50),                   -- 结果类型 (RED_WINS, BLACK_WINS, DRAW, etc.)
    reason          VARCHAR(50),                   -- 原因 (CHECKMATE, RESIGN, etc.)
    
    -- 元数据
    moves_json      JSONB,                         -- 着法历史 (JSON 数组)
    metadata        JSONB                          -- 其他元数据
);

CREATE INDEX idx_rooms_type ON rooms(type);
CREATE INDEX idx_rooms_status ON rooms(status);
CREATE INDEX idx_rooms_red_player ON rooms(red_player_id);
CREATE INDEX idx_rooms_black_player ON rooms(black_player_id);
CREATE INDEX idx_rooms_created_at ON rooms(created_at DESC);
CREATE INDEX idx_rooms_status_created ON rooms(status, created_at DESC);

-- =========================================
-- 4. 对局历史表 (game_histories)
-- =========================================
CREATE TABLE IF NOT EXISTS game_histories (
    id              BIGSERIAL PRIMARY KEY,
    room_id         VARCHAR(36) NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    
    -- 玩家信息
    red_player_id   BIGINT NOT NULL REFERENCES users(id),
    black_player_id BIGINT,                        -- PvE 时为 NULL
    
    -- 结果
    winner          INTEGER NOT NULL,              -- 0=红方, 1=黑方, -1=无(和棋)
    result          VARCHAR(50) NOT NULL,
    reason          VARCHAR(50),
    
    -- ELO 变化
    red_rating_before  INTEGER,
    red_rating_after   INTEGER,
    black_rating_before INTEGER,
    black_rating_after  INTEGER,
    
    -- 时间
    started_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    finished_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    duration        INTEGER,                       -- 持续时间(秒)
    moves_count     INTEGER,                       -- 总着法数
    
    -- 着法历史
    moves_json      JSONB NOT NULL,                -- 着法序列
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_game_histories_room_id ON game_histories(room_id);
CREATE INDEX idx_game_histories_red_player ON game_histories(red_player_id);
CREATE INDEX idx_game_histories_black_player ON game_histories(black_player_id);
CREATE INDEX idx_game_histories_finished_at ON game_histories(finished_at DESC);
CREATE INDEX idx_game_histories_winner ON game_histories(winner);

-- =========================================
-- 5. ELO 变更历史表 (elo_histories)
-- =========================================
CREATE TABLE IF NOT EXISTS elo_histories (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id         BIGINT REFERENCES game_histories(id),
    
    -- 积分变化
    rating_before   INTEGER NOT NULL,
    rating_after    INTEGER NOT NULL,
    rating_change   INTEGER NOT NULL,              -- 变化量 (正数=增加, 负数=减少)
    
    -- 对手信息
    opponent_id     BIGINT REFERENCES users(id),
    opponent_rating INTEGER,
    
    -- 游戏结果
    result          VARCHAR(20) NOT NULL,          -- WIN, LOSS, DRAW
    
    -- 详细
    game_type       VARCHAR(10),                   -- PVP, PVE
    difficulty      INTEGER,                        -- AI 难度 (PvE 时)
    
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_elo_histories_user_id ON elo_histories(user_id);
CREATE INDEX idx_elo_histories_game_id ON elo_histories(game_id);
CREATE INDEX idx_elo_histories_created_at ON elo_histories(created_at DESC);

-- =========================================
-- 6. AI 模型版本表 (model_versions)
-- =========================================
CREATE TABLE IF NOT EXISTS model_versions (
    id              BIGSERIAL PRIMARY KEY,
    version         VARCHAR(20) NOT NULL UNIQUE,  -- 版本号 (如 v1.0.0)
    description     TEXT,
    
    -- 模型文件
    file_path       VARCHAR(500) NOT NULL,        -- 模型文件路径
    file_size       BIGINT,                        -- 文件大小(字节)
    checksum        VARCHAR(64),                  -- SHA-256 校验和
    
    -- 模型信息
    architecture    VARCHAR(50) DEFAULT 'resnet19', -- 网络架构
    training_games  INTEGER DEFAULT 0,             -- 训练对局数
    
    -- ELO 评级
    elo_rating      INTEGER DEFAULT 1500,           -- 模型 ELO 评级
    parent_version  VARCHAR(20),                   -- 父版本
    
    -- 状态
    is_active       BOOLEAN DEFAULT FALSE,         -- 是否为当前活跃版本
    is_trained      BOOLEAN DEFAULT FALSE,         -- 训练是否完成
    
    -- 训练指标
    loss            DECIMAL(10, 6),
    accuracy        DECIMAL(5, 4),
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    trained_at      TIMESTAMP WITH TIME ZONE,
    deployed_at     TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_model_versions_version ON model_versions(version);
CREATE INDEX idx_model_versions_elo ON model_versions(elo_rating DESC);
CREATE INDEX idx_model_versions_active ON model_versions(is_active) WHERE is_active = TRUE;

-- =========================================
-- 7. 自对弈数据表 (selfplay_data) - 用于训练
-- =========================================
CREATE TABLE IF NOT EXISTS selfplay_data (
    id              BIGSERIAL PRIMARY KEY,
    model_version   VARCHAR(20) NOT NULL,
    
    -- 棋盘状态 (压缩格式)
    board_state     BYTEA NOT NULL,               -- 棋盘状态二进制
    policy_labels   FLOAT4[],                     -- 策略标签 (2085 维)
    value_label     FLOAT4,                        -- 价值标签 (+1/-1)
    
    -- 所属对局
    game_id         BIGINT,
    move_number     INTEGER,
    
    -- 时间戳
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_selfplay_model ON selfplay_data(model_version);
CREATE INDEX idx_selfplay_game ON selfplay_data(game_id);
CREATE INDEX idx_selfplay_created ON selfplay_data(created_at DESC);

-- =========================================
-- 触发器: 自动更新 updated_at
-- =========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_elo_ratings_updated_at
    BEFORE UPDATE ON elo_ratings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =========================================
-- 注释说明
-- =========================================
COMMENT ON TABLE users IS '用户表';
COMMENT ON TABLE elo_ratings IS 'ELO 积分表';
COMMENT ON TABLE rooms IS '房间表';
COMMENT ON TABLE game_histories IS '对局历史表';
COMMENT ON TABLE elo_histories IS 'ELO 变更历史表';
COMMENT ON TABLE model_versions IS 'AI 模型版本表';
COMMENT ON TABLE selfplay_data IS '自对弈训练数据表';
