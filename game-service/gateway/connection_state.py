"""Game Service v2.0 - WebSocket Gateway - Connection State Machine

Defines the connection lifecycle states and valid transitions.
"""

from enum import IntEnum


class ConnectionState(IntEnum):
    """WebSocket connection states."""
    UNAUTHENTICATED = 0  # 刚连接，未认证
    AUTHENTICATED = 1    # 已认证，在大厅
    IN_ROOM = 2          # 在房间中（对局中）
    MATCHMAKING = 3      # 在匹配队列中


# Valid state transitions
VALID_TRANSITIONS: dict[ConnectionState, set[ConnectionState]] = {
    ConnectionState.UNAUTHENTICATED: {ConnectionState.AUTHENTICATED},
    ConnectionState.AUTHENTICATED: {
        ConnectionState.IN_ROOM,
        ConnectionState.MATCHMAKING,
    },
    ConnectionState.IN_ROOM: {
        ConnectionState.AUTHENTICATED,  # 离开房间
    },
    ConnectionState.MATCHMAKING: {
        ConnectionState.AUTHENTICATED,  # 取消匹配
        ConnectionState.IN_ROOM,       # 匹配成功
    },
}


def can_transition(from_state: ConnectionState, to_state: ConnectionState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())
