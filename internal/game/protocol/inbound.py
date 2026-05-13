"""Inbound WebSocket messages from clients."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class InboundMessageType(str, Enum):
    """Client -> Server message types."""

    MOVE = "move"          # 走棋
    RESIGN = "resign"     # 认输
    DRAW_REQ = "draw_req" # 请求和棋
    DRAW_ANS = "draw_ans" # 和棋应答
    CHAT = "chat"         # 聊天消息
    PING = "ping"         # 心跳
    RECONNECT = "reconnect"  # 断线重连


@dataclass
class InboundMessage:
    """Base class for inbound messages."""
    type: InboundMessageType
    seq: int = 0
    data: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "InboundMessage":
        """Parse a dict into an InboundMessage."""
        msg_type = data.get("type", "")
        try:
            msg_type = InboundMessageType(msg_type)
        except ValueError:
            msg_type = InboundMessageType.PING

        return cls(
            type=msg_type,
            seq=data.get("seq", 0),
            data=data.get("data", {}),
        )


@dataclass
class MoveData:
    """Move message data."""
    from_pos: str  # e.g., "e7"
    to_pos: str    # e.g., "e6"

    @classmethod
    def from_dict(cls, data: dict) -> "MoveData":
        return cls(
            from_pos=data.get("from", data.get("from_pos", "")),
            to_pos=data.get("to", data.get("to_pos", "")),
        )


@dataclass
class DrawAnsData:
    """Draw answer message data."""
    accept: bool

    @classmethod
    def from_dict(cls, data: dict) -> "DrawAnsData":
        return cls(accept=data.get("accept", False))


@dataclass
class ChatData:
    """Chat message data."""
    content: str

    @classmethod
    def from_dict(cls, data: dict) -> "ChatData":
        return cls(content=data.get("content", ""))


@dataclass
class ReconnectData:
    """Reconnect message data."""
    token: str
    room_id: str

    @classmethod
    def from_dict(cls, data: dict) -> "ReconnectData":
        return cls(
            token=data.get("token", ""),
            room_id=data.get("room_id", ""),
        )
