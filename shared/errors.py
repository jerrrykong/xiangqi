"""Errors and exceptions for Xiangqi game."""
from dataclasses import dataclass


@dataclass
class XiangqiError(Exception):
    """象棋游戏错误基类"""
    code: int
    message: str
    detail: str = ""

    def __str__(self) -> str:
        if self.detail:
            return f"[{self.code}] {self.message}: {self.detail}"
        return f"[{self.code}] {self.message}"


# System errors
ERR_SYSTEM = XiangqiError(1000, "系统错误")
ERR_INTERNAL = XiangqiError(1001, "内部错误")
ERR_DATABASE = XiangqiError(1002, "数据库错误")
ERR_REDIS = XiangqiError(1003, "Redis 错误")
ERR_INVALID_PARAM = XiangqiError(1004, "参数错误")

# Auth errors
ERR_UNAUTHORIZED = XiangqiError(2001, "未认证")
ERR_TOKEN_EXPIRED = XiangqiError(2002, "Token 已过期")
ERR_TOKEN_INVALID = XiangqiError(2003, "无效的 Token")
ERR_WRONG_PASSWORD = XiangqiError(2004, "密码错误")
ERR_USER_NOT_FOUND = XiangqiError(2005, "用户不存在")
ERR_USER_EXISTS = XiangqiError(2006, "用户已存在")

# Room errors
ERR_ROOM_NOT_FOUND = XiangqiError(3001, "房间不存在")
ERR_ROOM_FULL = XiangqiError(3002, "房间已满")
ERR_ROOM_NOT_STARTED = XiangqiError(3003, "对局未开始")
ERR_ROOM_ALREADY_STARTED = XiangqiError(3004, "对局已开始")
ERR_NOT_ROOM_OWNER = XiangqiError(3005, "非房主")
ERR_NOT_YOUR_TURN = XiangqiError(3006, "非你的回合")
ERR_ALREADY_READY = XiangqiError(3007, "已准备")
ERR_NOT_READY = XiangqiError(3008, "未准备")

# Game errors
ERR_INVALID_MOVE = XiangqiError(4001, "无效着法")
ERR_MOVE_NOT_YOUR_TURN = XiangqiError(4002, "顺序错误")
ERR_GAME_NOT_STARTED = XiangqiError(4003, "游戏未开始")
ERR_GAME_ALREADY_OVER = XiangqiError(4004, "游戏已结束")
ERR_CHECK = XiangqiError(4005, "将军")


def error_from_code(code: int, detail: str = "") -> XiangqiError:
    """根据错误码返回错误实例"""
    error_map = {
        1000: ERR_SYSTEM,
        1001: ERR_INTERNAL,
        1002: ERR_DATABASE,
        1003: ERR_REDIS,
        1004: ERR_INVALID_PARAM,
        2001: ERR_UNAUTHORIZED,
        2002: ERR_TOKEN_EXPIRED,
        2003: ERR_TOKEN_INVALID,
        2004: ERR_WRONG_PASSWORD,
        2005: ERR_USER_NOT_FOUND,
        2006: ERR_USER_EXISTS,
        3001: ERR_ROOM_NOT_FOUND,
        3002: ERR_ROOM_FULL,
        3003: ERR_ROOM_NOT_STARTED,
        3004: ERR_ROOM_ALREADY_STARTED,
        3005: ERR_NOT_ROOM_OWNER,
        3006: ERR_NOT_YOUR_TURN,
        3007: ERR_ALREADY_READY,
        3008: ERR_NOT_READY,
        4001: ERR_INVALID_MOVE,
        4002: ERR_MOVE_NOT_YOUR_TURN,
        4003: ERR_GAME_NOT_STARTED,
        4004: ERR_GAME_ALREADY_OVER,
        4005: ERR_CHECK,
    }
    
    base_error = error_map.get(code, ERR_SYSTEM)
    return XiangqiError(
        code=base_error.code,
        message=base_error.message,
        detail=detail
    )
