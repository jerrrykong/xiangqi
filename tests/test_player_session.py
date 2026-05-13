"""Tests for player session."""
import pytest
import time

from internal.game.player_session import PlayerSession, ConnectionState


class TestPlayerSession:
    """Test PlayerSession class."""

    def test_session_creation(self):
        """Test session is created with default values."""
        session = PlayerSession()
        assert session.session_id is not None
        assert session.state == ConnectionState.CONNECTED
        assert session.room_id is None
        assert session.side is None
        assert session.user_id is None
        assert session.username is None

    def test_session_with_user(self):
        """Test session with user info."""
        session = PlayerSession(user_id=123, username="testuser")
        assert session.user_id == 123
        assert session.username == "testuser"

    def test_is_connected(self):
        """Test connection state check."""
        session = PlayerSession()
        assert session.is_connected() is True

        session.disconnect()
        assert session.is_connected() is False
        assert session.state == ConnectionState.DISCONNECTED

    def test_is_in_game(self):
        """Test in-game state check."""
        session = PlayerSession()
        assert session.is_in_game() is False

        session.room_id = "room-1"
        session.side = "red"
        assert session.is_in_game() is True

    def test_sides(self):
        """Test side checks."""
        session = PlayerSession()
        session.side = "red"
        assert session.is_red() is True
        assert session.is_black() is False

        session.side = "black"
        assert session.is_red() is False
        assert session.is_black() is True

    def test_update_activity(self):
        """Test activity timestamp update."""
        session = PlayerSession()
        time.sleep(0.01)
        session.update_activity()
        assert session.last_active > 0

    def test_deduct_time(self):
        """Test time deduction."""
        session = PlayerSession()
        session.remaining_time = 600

        remaining = session.deduct_time(10)
        assert remaining == 590

        remaining = session.deduct_time(600)
        assert remaining == 0

    def test_to_dict(self):
        """Test serialization."""
        session = PlayerSession(
            user_id=1,
            username="test",
            room_id="room-1",
            side="red",
        )
        d = session.to_dict()
        assert d["user_id"] == 1
        assert d["username"] == "test"
        assert d["room_id"] == "room-1"
        assert d["side"] == "red"
        assert d["state"] == "connected"
