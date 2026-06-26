"""Game Service v2.0 - AI Difficulty Controller

Maps difficulty levels (1-5) to search depth and think time.
"""

from dataclasses import dataclass


@dataclass
class DifficultyConfig:
    """AI difficulty configuration."""
    depth: int           # Minimax search depth
    max_time_ms: int     # Maximum think time in milliseconds


# Difficulty level → (search_depth, max_time_ms)
# 优化后同等深度更快 (Zobrist + MTD(f) + 7类位置表)，各档 +1 深度
DIFFICULTY_MAP: dict[int, DifficultyConfig] = {
    1: DifficultyConfig(depth=3, max_time_ms=2000),    # 入门
    2: DifficultyConfig(depth=4, max_time_ms=5000),    # 简单
    3: DifficultyConfig(depth=5, max_time_ms=8000),    # 中等（默认）
    4: DifficultyConfig(depth=6, max_time_ms=15000),   # 困难
    5: DifficultyConfig(depth=8, max_time_ms=30000),   # 大师
}


def get_difficulty_config(level: int) -> DifficultyConfig:
    """Get difficulty configuration for a given level (1-5).

    Returns default (level 3) if level is out of range.
    """
    return DIFFICULTY_MAP.get(level, DIFFICULTY_MAP[3])


def get_search_depth(level: int) -> int:
    """Get search depth for a difficulty level."""
    return get_difficulty_config(level).depth


def get_max_time_ms(level: int) -> int:
    """Get maximum think time in ms for a difficulty level."""
    return get_difficulty_config(level).max_time_ms
