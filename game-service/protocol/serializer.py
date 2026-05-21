"""Game Service v2.0 - Protocol - JSON Serializer

Handles JSON serialization/deserialization with dataclass support.
"""

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from protocol.message import Message


def serialize(data: Any) -> Any:
    """Recursively serialize dataclass instances and other types to JSON-compatible types."""
    if is_dataclass(data) and not isinstance(data, type):
        return {k: serialize(v) for k, v in asdict(data).items()}
    elif isinstance(data, list):
        return [serialize(item) for item in data]
    elif isinstance(data, dict):
        return {k: serialize(v) for k, v in data.items()}
    elif isinstance(data, (int, float, str, bool, type(None))):
        return data
    else:
        return str(data)


def deserialize_message(raw: str | bytes) -> Message:
    """Deserialize a JSON string into a Message object."""
    data = json.loads(raw)
    return Message.from_dict(data)


def to_json(msg: Message) -> str:
    """Serialize a Message to JSON string."""
    return msg.to_json()
