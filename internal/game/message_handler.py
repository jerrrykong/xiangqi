"""Message handler for processing WebSocket messages."""
import logging
from typing import Callable, Awaitable, Optional
import json
import time

from .protocol.inbound import (
    InboundMessage, InboundMessageType,
    MoveData, DrawAnsData, ChatData, ReconnectData,
)
from .protocol import outbound as out_msg
from .room_manager import RoomManager
from .player_session import PlayerSession


logger = logging.getLogger(__name__)


def _log(level: str, msg: str, **kwargs):
    """Structured logging helper."""
    parts = [msg]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    log_msg = " | ".join(parts)
    getattr(logger, level)(log_msg)


# Type alias for message handlers
MessageHandlerType = Callable[[PlayerSession, dict], Awaitable[Optional[dict]]]


class MessageHandler:
    """Handles all WebSocket message processing."""

    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager
        self._handlers = self._build_handlers()
        self._message_count = 0
        _log("info", "message_handler_init")

    def _build_handlers(self) -> dict:
        """Build the message handler map."""
        return {
            InboundMessageType.MOVE: self._handle_move,
            InboundMessageType.RESIGN: self._handle_resign,
            InboundMessageType.DRAW_REQ: self._handle_draw_req,
            InboundMessageType.DRAW_ANS: self._handle_draw_ans,
            InboundMessageType.CHAT: self._handle_chat,
            InboundMessageType.PING: self._handle_ping,
            InboundMessageType.RECONNECT: self._handle_reconnect,
        }

    async def handle(self, session: PlayerSession, raw_data: dict) -> Optional[dict]:
        """
        Process an incoming message.
        Returns a response dict, or None for no response.
        """
        start_time = time.time()
        self._message_count += 1

        try:
            msg = InboundMessage.from_dict(raw_data)
        except Exception as e:
            _log("warning", "msg_parse_error",
                 session_id=session.session_id,
                 error=str(e),
                 raw_data=str(raw_data)[:200])
            return out_msg.error_message(1003, f"Invalid message format: {e}")

        _log("debug", "msg_received",
             session_id=session.session_id,
             msg_type=msg.type.value if hasattr(msg.type, 'value') else str(msg.type),
             msg_count=self._message_count)

        handler = self._handlers.get(msg.type)
        if handler is None:
            _log("warning", "msg_unknown_type",
                 session_id=session.session_id,
                 msg_type=str(msg.type))
            return out_msg.error_message(1003, f"Unknown message type: {msg.type}")

        try:
            response = await handler(session, msg.data)
            duration_ms = int((time.time() - start_time) * 1000)
            _log("debug", "msg_handled",
                 session_id=session.session_id,
                 msg_type=str(msg.type),
                 has_response=response is not None,
                 duration_ms=duration_ms)
            return response
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            _log("error", "msg_handler_error",
                 session_id=session.session_id,
                 msg_type=str(msg.type),
                 error=str(e),
                 error_type=type(e).__name__,
                 duration_ms=duration_ms)
            return out_msg.error_message(1000, f"Internal error: {e}")

    async def _handle_move(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a move message."""
        _log("debug", "handle_move",
             session_id=session.session_id,
             room_id=session.room_id,
             side=session.side)

        move_data = MoveData.from_dict(data)
        from_pos = move_data.from_pos
        to_pos = move_data.to_pos

        if not from_pos or not to_pos:
            _log("warning", "handle_move_invalid_positions",
                 session_id=session.session_id,
                 from_pos=from_pos,
                 to_pos=to_pos)
            return out_msg.error_message(4001, "Missing from/to positions")

        _log("info", "handle_move_execute",
             session_id=session.session_id,
             room_id=session.room_id,
             from_pos=from_pos,
             to_pos=to_pos)

        success, response = await self.room_manager.handle_move(
            session.session_id, from_pos, to_pos
        )

        if not success:
            _log("warning", "handle_move_failed",
                 session_id=session.session_id,
                 from_pos=from_pos,
                 to_pos=to_pos,
                 error=response.get("data", {}).get("message", "unknown"))
            return response

        _log("info", "handle_move_success",
             session_id=session.session_id,
             room_id=session.room_id,
             from_pos=from_pos,
             to_pos=to_pos)

        return response

    async def _handle_resign(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a resign message."""
        _log("info", "handle_resign",
             session_id=session.session_id,
             room_id=session.room_id,
             side=session.side)

        success, response = await self.room_manager.handle_resign(
            session.session_id
        )

        if success:
            _log("info", "handle_resign_success",
                 session_id=session.session_id,
                 room_id=session.room_id)
        else:
            _log("warning", "handle_resign_failed",
                 session_id=session.session_id,
                 error=response.get("data", {}).get("message", "unknown"))

        return response

    async def _handle_draw_req(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a draw request."""
        _log("debug", "handle_draw_req",
             session_id=session.session_id,
             room_id=session.room_id,
             side=session.side)

        success, response = await self.room_manager.handle_draw_request(
            session.session_id
        )

        if success:
            _log("info", "handle_draw_req_sent",
                 session_id=session.session_id,
                 room_id=session.room_id)
        else:
            _log("warning", "handle_draw_req_failed",
                 session_id=session.session_id)

        return response

    async def _handle_draw_ans(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a draw answer."""
        ans_data = DrawAnsData.from_dict(data)
        _log("info", "handle_draw_ans",
             session_id=session.session_id,
             room_id=session.room_id,
             accept=ans_data.accept)

        success, response = await self.room_manager.handle_draw_answer(
            session.session_id, ans_data.accept
        )

        if success:
            _log("info", "handle_draw_ans_success",
                 session_id=session.session_id,
                 room_id=session.room_id,
                 accept=ans_data.accept)
        else:
            _log("warning", "handle_draw_ans_failed",
                 session_id=session.session_id)

        return response

    async def _handle_chat(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a chat message."""
        chat_data = ChatData.from_dict(data)
        content = chat_data.content.strip()

        _log("debug", "handle_chat",
             session_id=session.session_id,
             room_id=session.room_id,
             side=session.side,
             content_length=len(content))

        if not content:
            return None

        if len(content) > 200:
            _log("warning", "handle_chat_too_long",
                 session_id=session.session_id,
                 content_length=len(content))
            return out_msg.error_message(1003, "Message too long (max 200 chars)")

        # Forward to opponent
        room = await self.room_manager.get_room_by_session(session.session_id)
        if room:
            opponent = room.get_opponent_session(session.session_id)
            if opponent and opponent.is_connected():
                chat_msg = out_msg.chat_message(
                    from_side=session.side or "unknown",
                    content=content,
                )
                _log("debug", "handle_chat_forwarded",
                     session_id=session.session_id,
                     opponent_session=opponent.session_id)
                # TODO: send to opponent websocket

        return None  # Don't echo chat to sender

    async def _handle_ping(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a ping message."""
        session.update_activity()
        return out_msg.pong_message()

    async def _handle_reconnect(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a reconnect message."""
        reconnect_data = ReconnectData.from_dict(data)
        _log("info", "handle_reconnect",
             session_id=session.session_id,
             room_id=reconnect_data.room_id,
             token_provided=bool(reconnect_data.token))

        success, response = await self.room_manager.handle_reconnect(
            session=session,
            token=reconnect_data.token,
            room_id=reconnect_data.room_id,
        )

        if success:
            _log("info", "handle_reconnect_success",
                 session_id=session.session_id,
                 room_id=reconnect_data.room_id,
                 side=session.side)
        else:
            _log("warning", "handle_reconnect_failed",
                 session_id=session.session_id,
                 room_id=reconnect_data.room_id,
                 error=response.get("data", {}).get("message", "unknown"))

        return response
