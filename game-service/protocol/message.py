"""Game Service v2.0 - Protocol - Message Base

Defines the base message structure and serialization.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Message:
    """Base message structure for WebSocket communication.

    All messages follow the format:
    {
        "type": "xxx_yyy",     // 消息类型
        "seq": 1,              // 序列号（请求-响应对应）
        "data": {...},         // 消息数据
        "timestamp": 1234567890  // 时间戳（毫秒）
    }
    """
    type: str
    seq: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON transmission."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Deserialize from dict."""
        return cls(
            type=data.get("type", ""),
            seq=data.get("seq", 0),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", 0),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def make_response(msg_type: str, seq: int = 0, **kwargs) -> dict[str, Any]:
    """Create a response message dict."""
    return {
        "type": msg_type,
        "seq": seq,
        "data": kwargs,
        "timestamp": int(time.time() * 1000),
    }


def make_error(seq: int = 0, code: int = 0, message: str = "") -> dict[str, Any]:
    """Create an error response message dict."""
    return {
        "type": "error",
        "seq": seq,
        "data": {
            "code": code,
            "message": message,
        },
        "timestamp": int(time.time() * 1000),
    }
