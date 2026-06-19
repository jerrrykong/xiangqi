"""Game Service v2.0 - Configuration Loader

Loads configuration from config.yaml with environment variable overrides.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    workers: int = 1


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    user: str = "xiangqi"
    password: str = "xiangqi"
    dbname: str = "xiangqi"
    min_pool_size: int = 5
    max_pool_size: int = 20

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"


@dataclass
class JWTConfig:
    secret: str = "your-jwt-secret-change-in-production"
    algorithm: str = "HS256"
    expire_hours: int = 168
    refresh_expire_hours: int = 720


@dataclass
class GameConfig:
    default_initial_time: int = 600
    default_increment: int = 10
    max_think_time: int = 300
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 60
    disconnect_timeout: int = 300  # 断线超时(秒)，非Playing状态下超时视为离开房间
    # Persistence and AI timing
    persist_every_n_moves: int = 5
    ai_ready_delay: float = 0.25
    ai_rematch_delay: float = 0.5
    rematch_timeout: float = 60.0


@dataclass
class MatchConfig:
    tick_interval: int = 2
    initial_elo_range: int = 200
    normal_elo_range: int = 100
    high_elo_range: int = 150
    high_elo_threshold: int = 2000
    expand_rate: int = 50
    expand_interval: int = 30
    max_wait_time: int = 180


@dataclass
class AIConfig:
    default_difficulty: int = 3
    max_threads: int = 4


@dataclass
class InternalConfig:
    secret: str = "internal-service-secret-key"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_dir: str = "logs"
    filename: str = "game-service.log"
    when: str = "midnight"       # 滚动周期: midnight / D / H / W0-W6
    interval: int = 1            # 滚动间隔
    backup_count: int = 30       # 保留最近N天的日志
    encoding: str = "utf-8"


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    jwt: JWTConfig = field(default_factory=JWTConfig)
    game: GameConfig = field(default_factory=GameConfig)
    match: MatchConfig = field(default_factory=MatchConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    internal: InternalConfig = field(default_factory=InternalConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _apply_env_overrides(config: Config) -> None:
    """Override config values from environment variables.

    Environment variables take the form: GS_{SECTION}_{KEY}
    Example: GS_DATABASE_HOST=db.example.com
    """
    env_map = {
        "GS_SERVER_HOST": ("server", "host", str),
        "GS_SERVER_PORT": ("server", "port", int),
        "GS_DATABASE_HOST": ("database", "host", str),
        "GS_DATABASE_PORT": ("database", "port", int),
        "GS_DATABASE_USER": ("database", "user", str),
        "GS_DATABASE_PASSWORD": ("database", "password", str),
        "GS_DATABASE_DBNAME": ("database", "dbname", str),
        "GS_DATABASE_MIN_POOL_SIZE": ("database", "min_pool_size", int),
        "GS_DATABASE_MAX_POOL_SIZE": ("database", "max_pool_size", int),
        "GS_JWT_SECRET": ("jwt", "secret", str),
        "GS_JWT_ALGORITHM": ("jwt", "algorithm", str),
        "GS_JWT_EXPIRE_HOURS": ("jwt", "expire_hours", int),
        "GS_INTERNAL_SECRET": ("internal", "secret", str),
        # Game-level overrides
        "GS_GAME_PERSIST_EVERY_N_MOVES": ("game", "persist_every_n_moves", int),
        "GS_GAME_AI_READY_DELAY": ("game", "ai_ready_delay", float),
        "GS_GAME_AI_REMATCH_DELAY": ("game", "ai_rematch_delay", float),
        "GS_GAME_REMATCH_TIMEOUT": ("game", "rematch_timeout", float),
    }

    for env_key, (section, attr, converter) in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            section_obj = getattr(config, section)
            setattr(section_obj, attr, converter(value))


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file with environment variable overrides."""
    config = Config()

    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data:
            if "server" in data:
                for k, v in data["server"].items():
                    if hasattr(config.server, k):
                        setattr(config.server, k, v)
            if "database" in data:
                for k, v in data["database"].items():
                    if hasattr(config.database, k):
                        setattr(config.database, k, v)
            if "jwt" in data:
                for k, v in data["jwt"].items():
                    if hasattr(config.jwt, k):
                        setattr(config.jwt, k, v)
            if "game" in data:
                for k, v in data["game"].items():
                    if hasattr(config.game, k):
                        setattr(config.game, k, v)
            if "match" in data:
                for k, v in data["match"].items():
                    if hasattr(config.match, k):
                        setattr(config.match, k, v)
            if "ai" in data:
                for k, v in data["ai"].items():
                    if hasattr(config.ai, k):
                        setattr(config.ai, k, v)
            if "internal" in data:
                for k, v in data["internal"].items():
                    if hasattr(config.internal, k):
                        setattr(config.internal, k, v)
            if "logging" in data:
                for k, v in data["logging"].items():
                    if hasattr(config.logging, k):
                        setattr(config.logging, k, v)

    _apply_env_overrides(config)
    return config
