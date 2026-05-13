-- Initialize database schema for Chinese Chess Web Service

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(32) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(64),
    avatar VARCHAR(255),
    is_admin BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- ELO ratings table
CREATE TABLE IF NOT EXISTS elo_ratings (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER DEFAULT 1500,
    games_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ELO history table
CREATE TABLE IF NOT EXISTS elo_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL,
    change INTEGER NOT NULL,
    game_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rooms table
CREATE TABLE IF NOT EXISTS rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(8) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'waiting',
    difficulty INTEGER,
    red_user_id BIGINT REFERENCES users(id),
    black_user_id BIGINT REFERENCES users(id),
    red_ready BOOLEAN DEFAULT FALSE,
    black_ready BOOLEAN DEFAULT FALSE,
    winner VARCHAR(8),
    game_id UUID,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

-- Game history table
CREATE TABLE IF NOT EXISTS game_history (
    id BIGSERIAL PRIMARY KEY,
    room_id UUID NOT NULL REFERENCES rooms(id),
    winner VARCHAR(8) NOT NULL,
    result INTEGER NOT NULL,
    total_moves INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    pve_level INTEGER,
    red_user_id BIGINT REFERENCES users(id),
    black_user_id BIGINT REFERENCES users(id)
);

-- Model versions table
CREATE TABLE IF NOT EXISTS model_versions (
    id BIGSERIAL PRIMARY KEY,
    version VARCHAR(32) UNIQUE NOT NULL,
    model_path VARCHAR(255) NOT NULL,
    elo_score INTEGER,
    status VARCHAR(16) NOT NULL DEFAULT 'training',
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_elo_history_user_id ON elo_history(user_id);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_created_by ON rooms(created_by);
CREATE INDEX IF NOT EXISTS idx_game_history_room_id ON game_history(room_id);
CREATE INDEX IF NOT EXISTS idx_game_history_red_user_id ON game_history(red_user_id);
CREATE INDEX IF NOT EXISTS idx_game_history_black_user_id ON game_history(black_user_id);
