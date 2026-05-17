"""Outbound WebSocket messages to clients.

Message format: flat JSON  { "type": "...", field1: ..., field2: ... }
No nested "data" wrapper — matches the TypeScript client types exactly.
"""
from enum import Enum
from typing import Any, Optional, List


class OutboundMessageType(str, Enum):
    """Server -> Client message types."""

    # 连接/状态
    GAME_START = "game_start"        # 对局开始
    STATE_SYNC = "state_sync"        # 状态同步（断线重连）
    GAME_OVER = "game_over"          # 对局结束
    ERROR = "error"                  # 错误通知

    # 对局中
    MOVE_RESULT = "move_result"      # 着法结果（自己的着法）
    OPPONENT_MOVE = "opponent_move"  # 对手落子通知
    CHECK = "check"                  # 将军通知
    AI_THINKING = "ai_thinking"      # AI 正在思考
    AI_MOVE = "ai_move"              # AI 落子
    TIMEOUT_WARNING = "timeout_warning"  # 超时预警

    # 和棋
    DRAW_REQUEST = "draw_req"        # 收到和棋请求  (matches MsgType.DrawNotify client-side)
    DRAW_NOTIFY = "draw_notify"      # 和棋通知
    DRAW_ANSWERED = "draw_answered"  # 和棋应答通知
    DRAW_RESULT = "draw_result"      # 和棋结果

    # 断线
    OPPONENT_LEFT = "opponent_left"  # 对手断线
    OPPONENT_REJOIN = "opponent_rejoin"  # 对手重连

    # 心跳
    PONG = "pong"                    # 心跳响应

    # 等待
    WAITING = "waiting"              # 等待对手

    # 聊天
    CHAT = "chat"                    # 聊天消息


def _side_to_color(side: str) -> int:
    """Convert side string to color int. red=0, black=1."""
    return 0 if side == "red" else 1


def error_message(code: int, message: str) -> dict:
    """Create an error message.
    Client type: ErrorMessage { type, code, message }
    """
    return {
        "type": OutboundMessageType.ERROR.value,
        "code": code,
        "message": message,
    }


def game_start_message(
    room_id: str,
    your_side: str,  # "red" or "black"
    red_time: int = 600,
    black_time: int = 600,
) -> dict:
    """Create a game start message.
    Client type: GameStartMessage { type, room_id, your_color, red_time, black_time }
    """
    return {
        "type": OutboundMessageType.GAME_START.value,
        "room_id": room_id,
        "your_color": _side_to_color(your_side),
        "red_time": red_time,
        "black_time": black_time,
    }


def state_sync_message(
    room_id: str,
    board: List[List[int]],
    turn: str,  # "red" or "black"
    move_no: int,
    red_time: int,
    black_time: int,
    your_side: str,
) -> dict:
    """Create a state sync message (for reconnection).
    Client type: StateSyncMessage { type, board, turn, red_time, black_time, room_id, your_color }
    """
    return {
        "type": OutboundMessageType.STATE_SYNC.value,
        "room_id": room_id,
        "board": board,
        "turn": _side_to_color(turn),
        "move_no": move_no,
        "red_time": red_time,
        "black_time": black_time,
        "your_color": _side_to_color(your_side),
    }


def opponent_move_message(
    move: dict,  # { from_row, from_col, to_row, to_col }
    red_time: int,
    black_time: int,
) -> dict:
    """Create an opponent move message.
    Client type: OpponentMoveMessage { type, move, red_time, black_time }
    """
    return {
        "type": OutboundMessageType.OPPONENT_MOVE.value,
        "move": move,
        "red_time": red_time,
        "black_time": black_time,
    }


def move_result_message(
    move: dict,  # { from_row, from_col, to_row, to_col }
    red_time: int,
    black_time: int,
) -> dict:
    """Create a move result message (echo back to the moving player)."""
    return {
        "type": OutboundMessageType.MOVE_RESULT.value,
        "move": move,
        "red_time": red_time,
        "black_time": black_time,
    }


def game_over_message(
    winner: str,  # "red", "black", or "none"
    result: str,
    reason: str,
) -> dict:
    """Create a game over message.
    Client type: GameOverMessage { type, result, reason, winner }
    winner: -1=none, 0=red, 1=black (int)
    """
    winner_int = -1
    if winner == "red":
        winner_int = 0
    elif winner == "black":
        winner_int = 1
    return {
        "type": OutboundMessageType.GAME_OVER.value,
        "result": result,
        "reason": reason,
        "winner": winner_int,
    }


def check_message(
    by_piece: int,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
) -> dict:
    """Create a check (将军) message.
    Client type: CheckMessage { type, by_piece, from_row, from_col, to_row, to_col }
    """
    return {
        "type": OutboundMessageType.CHECK.value,
        "by_piece": by_piece,
        "from_row": from_row,
        "from_col": from_col,
        "to_row": to_row,
        "to_col": to_col,
    }


def opponent_left_message(
    reason: str = "disconnect",
    timeout: int = 60,
) -> dict:
    """Create an opponent left message."""
    return {
        "type": OutboundMessageType.OPPONENT_LEFT.value,
        "reason": reason,
        "timeout": timeout,
    }


def opponent_rejoin_message(username: str) -> dict:
    """Create an opponent rejoin message."""
    return {
        "type": OutboundMessageType.OPPONENT_REJOIN.value,
        "username": username,
    }


def draw_notify_message(from_side: str) -> dict:
    """Create a draw request notification (Server -> Client).
    Client type: DrawNotifyMessage { type, from, token? }
    """
    return {
        "type": OutboundMessageType.DRAW_NOTIFY.value,
        "from": from_side,
    }


def pong_message(time_val: int = 0) -> dict:
    """Create a pong response.
    Client type: PongMessage { type, time }
    """
    return {
        "type": OutboundMessageType.PONG.value,
        "time": time_val,
    }


def ai_thinking_message() -> dict:
    """Create an AI thinking message."""
    return {
        "type": OutboundMessageType.AI_THINKING.value,
    }


def ai_move_message(move: dict, red_time: int, black_time: int) -> dict:
    """Create an AI move message."""
    return {
        "type": OutboundMessageType.AI_MOVE.value,
        "move": move,
        "red_time": red_time,
        "black_time": black_time,
    }


def timeout_warning_message(remaining: int) -> dict:
    """Create a timeout warning message."""
    return {
        "type": OutboundMessageType.TIMEOUT_WARNING.value,
        "remaining": remaining,
    }


def chat_message(from_side: str, content: str) -> dict:
    """Create a chat message."""
    return {
        "type": OutboundMessageType.CHAT.value,
        "from": from_side,
        "content": content,
    }


def waiting_message(room_id: str, side: str) -> dict:
    """Create a waiting message."""
    return {
        "type": OutboundMessageType.WAITING.value,
        "room_id": room_id,
        "your_color": _side_to_color(side),
    }
