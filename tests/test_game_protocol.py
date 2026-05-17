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
        """Test error message creation (flat format, no data wrapper)."""
        msg = out_msg.error_message(4001, "invalid move")
        assert msg["type"] == "error"
        assert msg["code"] == 4001
        assert msg["message"] == "invalid move"

    def test_game_start_message(self):
        """Test game start message (flat format with your_color int)."""
        msg = out_msg.game_start_message(
            room_id="room-1",
            your_side="red",
            red_time=600,
            black_time=600,
        )
        assert msg["type"] == "game_start"
        assert msg["room_id"] == "room-1"
        assert msg["your_color"] == 0  # red = 0

    def test_game_start_message_black(self):
        """Test game start message for black side."""
        msg = out_msg.game_start_message(
            room_id="room-1",
            your_side="black",
            red_time=600,
            black_time=600,
        )
        assert msg["your_color"] == 1  # black = 1

    def test_state_sync_message(self):
        """Test state sync message (flat format)."""
        board = [[0]*9 for _ in range(10)]
        msg = out_msg.state_sync_message(
            room_id="room-1",
            board=board,
            turn="red",
            move_no=5,
            red_time=580,
            black_time=600,
            your_side="red",
        )
        assert msg["type"] == "state_sync"
        assert msg["move_no"] == 5
        assert msg["turn"] == 0  # red = 0
        assert msg["your_color"] == 0

    def test_move_result_message(self):
        """Test move result message (flat format with move dict)."""
        move = {"from_row": 6, "from_col": 4, "to_row": 4, "to_col": 4}
        msg = out_msg.move_result_message(
            move=move,
            red_time=580,
            black_time=600,
        )
        assert msg["type"] == "move_result"
        assert msg["move"]["from_row"] == 6
        assert msg["move"]["to_row"] == 4
        assert msg["red_time"] == 580

    def test_game_over_message(self):
        """Test game over message (flat format with winner int)."""
        msg = out_msg.game_over_message(
            winner="red",
            result="RED_WINS",
            reason="CHECKMATE",
        )
        assert msg["type"] == "game_over"
        assert msg["winner"] == 0  # red = 0
        assert msg["result"] == "RED_WINS"
        assert msg["reason"] == "CHECKMATE"

    def test_game_over_message_black_wins(self):
        """Test game over message with black winner."""
        msg = out_msg.game_over_message(
            winner="black",
            result="BLACK_WINS",
            reason="CHECKMATE",
        )
        assert msg["winner"] == 1  # black = 1

    def test_game_over_message_draw(self):
        """Test game over message with no winner (draw)."""
        msg = out_msg.game_over_message(
            winner="none",
            result="DRAW",
            reason="AGREED",
        )
        assert msg["winner"] == -1  # none = -1

    def test_pong_message(self):
        """Test pong message (flat format)."""
        msg = out_msg.pong_message(time_val=12345)
        assert msg["type"] == "pong"
        assert msg["time"] == 12345

    def test_ai_thinking_message(self):
        """Test AI thinking message."""
        msg = out_msg.ai_thinking_message()
        assert msg["type"] == "ai_thinking"

    def test_ai_move_message(self):
        """Test AI move message (flat format with move dict)."""
        move = {"from_row": 0, "from_col": 0, "to_row": 2, "to_col": 0}
        msg = out_msg.ai_move_message(
            move=move,
            red_time=580,
            black_time=600,
        )
        assert msg["type"] == "ai_move"
        assert msg["move"]["from_row"] == 0
        assert msg["move"]["to_row"] == 2
        assert msg["red_time"] == 580
        assert msg["black_time"] == 600

    def test_opponent_left_message(self):
        """Test opponent left message (flat format)."""
        msg = out_msg.opponent_left_message(reason="disconnect", timeout=60)
        assert msg["type"] == "opponent_left"
        assert msg["reason"] == "disconnect"
        assert msg["timeout"] == 60

    def test_waiting_message(self):
        """Test waiting message (flat format with your_color int)."""
        msg = out_msg.waiting_message(room_id="room-1", side="red")
        assert msg["type"] == "waiting"
        assert msg["room_id"] == "room-1"
        assert msg["your_color"] == 0  # red = 0

    def test_chat_message(self):
        """Test chat message."""
        msg = out_msg.chat_message(from_side="red", content="你好")
        assert msg["type"] == "chat"
        assert msg["from"] == "red"
        assert msg["content"] == "你好"

    def test_timeout_warning_message(self):
        """Test timeout warning message."""
        msg = out_msg.timeout_warning_message(remaining=30)
        assert msg["type"] == "timeout_warning"
        assert msg["remaining"] == 30

    def test_opponent_rejoin_message(self):
        """Test opponent rejoin message."""
        msg = out_msg.opponent_rejoin_message(username="player1")
        assert msg["type"] == "opponent_rejoin"
        assert msg["username"] == "player1"

    def test_draw_notify_message(self):
        """Test draw notify message."""
        msg = out_msg.draw_notify_message(from_side="red")
        assert msg["type"] == "draw_notify"
        assert msg["from"] == "red"
