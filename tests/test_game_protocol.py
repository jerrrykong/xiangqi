"""Tests for WebSocket protocol."""
import pytest

from internal.game.protocol.inbound import (
    InboundMessage, InboundMessageType, MoveData, DrawAnsData,
    ChatData, ReconnectData,
)
from internal.game.protocol import outbound as out_msg


class TestInboundMessage:
    """Test inbound message parsing."""

    def test_parse_move_message(self):
        """Test parsing a move message."""
        data = {
            "type": "move",
            "seq": 1,
            "data": {"from": "e7", "to": "e6"},
        }
        msg = InboundMessage.from_dict(data)
        assert msg.type == InboundMessageType.MOVE
        assert msg.seq == 1
        assert msg.data["from"] == "e7"

    def test_parse_resign_message(self):
        """Test parsing a resign message."""
        data = {"type": "resign", "data": {}}
        msg = InboundMessage.from_dict(data)
        assert msg.type == InboundMessageType.RESIGN

    def test_parse_unknown_type_defaults_to_ping(self):
        """Test unknown message type defaults to ping."""
        data = {"type": "unknown_type", "data": {}}
        msg = InboundMessage.from_dict(data)
        assert msg.type == InboundMessageType.PING

    def test_move_data_from_dict(self):
        """Test MoveData parsing."""
        data = MoveData.from_dict({"from": "a0", "to": "a2"})
        assert data.from_pos == "a0"
        assert data.to_pos == "a2"

    def test_draw_ans_data(self):
        """Test DrawAnsData parsing."""
        data = DrawAnsData.from_dict({"accept": True})
        assert data.accept is True

        data = DrawAnsData.from_dict({"accept": False})
        assert data.accept is False

    def test_chat_data(self):
        """Test ChatData parsing."""
        data = ChatData.from_dict({"content": "你好"})
        assert data.content == "你好"

    def test_reconnect_data(self):
        """Test ReconnectData parsing."""
        data = ReconnectData.from_dict({
            "token": "abc123",
            "room_id": "room-1",
        })
        assert data.token == "abc123"
        assert data.room_id == "room-1"


class TestOutboundMessage:
    """Test outbound message creation."""

    def test_error_message(self):
        """Test error message creation."""
        msg = out_msg.error_message(4001, "invalid move")
        assert msg["type"] == "error"
        assert msg["data"]["code"] == 4001
        assert msg["data"]["message"] == "invalid move"

    def test_game_start_message(self):
        """Test game start message."""
        msg = out_msg.game_start_message(
            room_id="room-1",
            your_side="red",
            red_time=600,
            black_time=600,
        )
        assert msg["type"] == "game_start"
        assert msg["data"]["room_id"] == "room-1"
        assert msg["data"]["your_side"] == "red"

    def test_state_sync_message(self):
        """Test state sync message."""
        msg = out_msg.state_sync_message(
            room_id="room-1",
            board=[[0]*9 for _ in range(10)],
            turn="red",
            move_no=5,
            red_time=580,
            black_time=600,
            your_side="red",
        )
        assert msg["type"] == "state_sync"
        assert msg["data"]["move_no"] == 5
        assert msg["data"]["turn"] == "red"

    def test_move_result_message(self):
        """Test move result message."""
        msg = out_msg.move_result_message(
            player="red",
            from_pos="e7",
            to_pos="e6",
            captured=0,
            check=False,
            red_time=580,
            black_time=600,
        )
        assert msg["type"] == "move_result"
        assert msg["data"]["from"] == "e7"
        assert msg["data"]["to"] == "e6"

    def test_game_over_message(self):
        """Test game over message."""
        msg = out_msg.game_over_message(
            winner="red",
            result="RED_WINS",
            reason="CHECKMATE",
        )
        assert msg["type"] == "game_over"
        assert msg["data"]["winner"] == "red"

    def test_pong_message(self):
        """Test pong message."""
        msg = out_msg.pong_message()
        assert msg["type"] == "pong"
        assert msg["data"] == {}

    def test_ai_thinking_message(self):
        """Test AI thinking message."""
        msg = out_msg.ai_thinking_message()
        assert msg["type"] == "ai_thinking"

    def test_ai_move_message(self):
        """Test AI move message."""
        msg = out_msg.ai_move_message(
            from_pos="a0",
            to_pos="a2",
            captured=0,
        )
        assert msg["type"] == "ai_move"
        assert msg["data"]["from"] == "a0"

    def test_opponent_left_message(self):
        """Test opponent left message."""
        msg = out_msg.opponent_left_message(reason="disconnect", timeout=60)
        assert msg["type"] == "opponent_left"
        assert msg["data"]["reason"] == "disconnect"
        assert msg["data"]["timeout"] == 60
