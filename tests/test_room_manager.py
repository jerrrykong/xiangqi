"""Tests for room manager."""
import pytest
import asyncio

from internal.game.room_manager import Room, RoomManager, RoomState
from internal.game.player_session import PlayerSession


class TestRoom:
    """Test Room class."""

    def test_room_creation(self):
        """Test room is created with defaults."""
        room = Room(room_id="test-room", room_type="pvp")
        assert room.room_id == "test-room"
        assert room.room_type == "pvp"
        assert room.state == RoomState.WAITING
        assert room.is_empty() is True
        assert room.is_full() is False

    def test_assign_red(self):
        """Test red side assignment."""
        room = Room(room_id="test", room_type="pvp")
        session = PlayerSession(user_id=1, username="player1")

        result = room.assign_red(session)
        assert result is True
        assert room.red_session == session
        assert session.side == "red"
        assert session.room_id == "test"

    def test_assign_black(self):
        """Test black side assignment."""
        room = Room(room_id="test", room_type="pvp")
        session = PlayerSession(user_id=1, username="player1")

        result = room.assign_black(session)
        assert result is True
        assert room.black_session == session
        assert session.side == "black"

    def test_cannot_assign_same_side_twice(self):
        """Test cannot assign same side twice."""
        room = Room(room_id="test", room_type="pvp")
        session1 = PlayerSession(user_id=1, username="player1")
        session2 = PlayerSession(user_id=2, username="player2")

        room.assign_red(session1)
        result = room.assign_red(session2)
        assert result is False

    def test_is_full(self):
        """Test room fullness check."""
        room = Room(room_id="test", room_type="pvp")
        assert room.is_full() is False

        room.assign_red(PlayerSession(user_id=1, username="p1"))
        assert room.is_full() is False

        room.assign_black(PlayerSession(user_id=2, username="p2"))
        assert room.is_full() is True

    def test_has_player(self):
        """Test player check."""
        room = Room(room_id="test", room_type="pvp")
        session1 = PlayerSession(user_id=1, username="p1")
        session2 = PlayerSession(user_id=2, username="p2")

        room.assign_red(session1)
        assert room.has_player(session1.session_id) is True
        assert room.has_player(session2.session_id) is False

    def test_get_side(self):
        """Test getting side by session ID."""
        room = Room(room_id="test", room_type="pvp")
        session = PlayerSession(user_id=1, username="p1")

        room.assign_red(session)
        assert room.get_side(session.session_id) == "red"

    def test_get_opponent_session(self):
        """Test getting opponent session."""
        room = Room(room_id="test", room_type="pvp")
        red = PlayerSession(user_id=1, username="red")
        black = PlayerSession(user_id=2, username="black")

        room.assign_red(red)
        room.assign_black(black)

        assert room.get_opponent_session(red.session_id) == black
        assert room.get_opponent_session(black.session_id) == red

    def test_start_game(self):
        """Test starting a game."""
        room = Room(room_id="test", room_type="pvp")
        room.assign_red(PlayerSession(user_id=1, username="red"))
        room.assign_black(PlayerSession(user_id=2, username="black"))
        room.state = RoomState.READY  # Must be READY first

        room.start_game()
        assert room.state == RoomState.PLAYING
        assert room.started_at is not None
        assert room.game is not None


class TestRoomManager:
    """Test RoomManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh room manager."""
        return RoomManager()

    @pytest.mark.asyncio
    async def test_create_room(self, manager):
        """Test creating a room."""
        room = await manager.create_room(room_type="pvp")
        assert room is not None
        assert room.room_type == "pvp"
        assert room.state == RoomState.WAITING

    @pytest.mark.asyncio
    async def test_get_room(self, manager):
        """Test getting a room by ID."""
        room = await manager.create_room(room_type="pvp")
        retrieved = await manager.get_room(room.room_id)
        assert retrieved == room

    @pytest.mark.asyncio
    async def test_join_room(self, manager):
        """Test joining a room."""
        room = await manager.create_room(room_type="pvp")
        session = PlayerSession(user_id=1, username="player1")

        success, msg = await manager.join_room(room.room_id, session)
        assert success is True
        assert room.red_session == session

    @pytest.mark.asyncio
    async def test_join_room_full(self, manager):
        """Test joining a full room."""
        room = await manager.create_room(room_type="pvp")
        session1 = PlayerSession(user_id=1, username="p1")
        session2 = PlayerSession(user_id=2, username="p2")

        await manager.join_room(room.room_id, session1)
        success, msg = await manager.join_room(room.room_id, session2)
        assert success is True
        assert room.black_session == session2

        # Third player should fail
        session3 = PlayerSession(user_id=3, username="p3")
        success, msg = await manager.join_room(room.room_id, session3)
        assert success is False

    @pytest.mark.asyncio
    async def test_game_starts_when_full(self, manager):
        """Test game starts when both players join."""
        room = await manager.create_room(room_type="pvp")
        red = PlayerSession(user_id=1, username="red")
        black = PlayerSession(user_id=2, username="black")

        await manager.join_room(room.room_id, red)
        assert room.state == RoomState.WAITING

        await manager.join_room(room.room_id, black)
        assert room.state == RoomState.PLAYING
        assert room.game is not None

    @pytest.mark.asyncio
    async def test_leave_room(self, manager):
        """Test leaving a room."""
        room = await manager.create_room(room_type="pvp")
        session = PlayerSession(user_id=1, username="p1")

        await manager.join_room(room.room_id, session)
        assert room.red_session == session

        success = await manager.leave_room(session.session_id)
        assert success is True
        assert room.red_session is None

    @pytest.mark.asyncio
    async def test_list_active_rooms(self, manager):
        """Test listing active rooms."""
        room1 = await manager.create_room(room_type="pvp")
        room2 = await manager.create_room(room_type="pvp")
        room3 = await manager.create_room(room_type="pve")

        rooms = manager.list_active_rooms()
        assert len(rooms) == 3

        assert manager.count_active_rooms() == 3
