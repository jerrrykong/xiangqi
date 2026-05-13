"""Message handler for processing WebSocket messages."""
import logging
from typing import Callable, Awaitable, Optional
import json

from .protocol.inbound import (
    InboundMessage, InboundMessageType,
    MoveData, DrawAnsData, ChatData, ReconnectData,
)
from .protocol import outbound as out_msg
from .room_manager import RoomManager
from .player_session import PlayerSession


logger = logging.getLogger(__name__)


# Type alias for message handlers
MessageHandlerType = Callable[[PlayerSession, dict], Awaitable[Optional[dict]]]


class MessageHandler:
    """Handles all WebSocket message processing."""

    def __init__(self, room_manager: RoomManager):
        self.room_manager = room_manager
        self._handlers = self._build_handlers()

    def _build_handlers(self) -> dict[str, MessageHandlerType]:
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
        try:
            msg = InboundMessage.from_dict(raw_data)
        except Exception as e:
            logger.warning(f"Failed to parse message: {e}")
            return out_msg.error_message(1003, f"Invalid message format: {e}")

        handler = self._handlers.get(msg.type)
        if handler is None:
            return out_msg.error_message(1003, f"Unknown message type: {msg.type}")

        try:
            response = await handler(session, msg.data)
            return response
        except Exception as e:
            logger.error(f"Error handling message {msg.type}: {e}", exc_info=True)
            return out_msg.error_message(1000, f"Internal error: {e}")

    async def _handle_move(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a move message."""
        move_data = MoveData.from_dict(data)
        from_pos = move_data.from_pos
        to_pos = move_data.to_pos

        if not from_pos or not to_pos:
            return out_msg.error_message(4001, "Missing from/to positions")

        success, response = await self.room_manager.handle_move(
            session.session_id, from_pos, to_pos
        )

        if not success:
            return response

        return response

    async def _handle_resign(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a resign message."""
        success, response = await self.room_manager.handle_resign(
            session.session_id
        )
        return response if success else response

    async def _handle_draw_req(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a draw request."""
        success, response = await self.room_manager.handle_draw_request(
            session.session_id
        )
        return response if success else response

    async def _handle_draw_ans(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a draw answer."""
        ans_data = DrawAnsData.from_dict(data)
        success, response = await self.room_manager.handle_draw_answer(
            session.session_id, ans_data.accept
        )
        return response if success else response

    async def _handle_chat(
        self,
        session: PlayerSession,
        data: dict,
    ) -> Optional[dict]:
        """Handle a chat message."""
        chat_data = ChatData.from_dict(data)
        content = chat_data.content.strip()

        if not content:
            return None

        if len(content) > 200:
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
        success, response = await self.room_manager.handle_reconnect(
            session=session,
            token=reconnect_data.token,
            room_id=reconnect_data.room_id,
        )
        return response if success else response
