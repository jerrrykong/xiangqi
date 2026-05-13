"""Protocol definitions for WebSocket messages."""
from .inbound import InboundMessage, InboundMessageType
from .outbound import OutboundMessageType

__all__ = [
    "InboundMessage",
    "InboundMessageType",
    "OutboundMessageType",
]
