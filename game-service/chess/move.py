"""Game Service v2.0 - Move Data Structure

Move dataclass for chess moves.
Migrated from shared/protocol.py for self-contained chess module.
"""
from dataclasses import dataclass


@dataclass
class Move:
    """着法"""
    from_col: int
    from_row: int
    to_col: int
    to_row: int

    def __post_init__(self):
        self.from_col = int(self.from_col)
        self.from_row = int(self.from_row)
        self.to_col = int(self.to_col)
        self.to_row = int(self.to_row)

    def is_valid(self) -> bool:
        return (0 <= self.from_col <= 8 and 0 <= self.from_row <= 9 and
                0 <= self.to_col <= 8 and 0 <= self.to_row <= 9)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move):
            return False
        return (self.from_col == other.from_col and
                self.from_row == other.from_row and
                self.to_col == other.to_col and
                self.to_row == other.to_row)

    def __hash__(self) -> int:
        return hash((self.from_col, self.from_row, self.to_col, self.to_row))

    def __repr__(self) -> str:
        return f"Move({self.from_col},{self.from_row}->{self.to_col},{self.to_row})"

    def encode(self) -> int:
        """将着法编码为整数 (0-2084)"""
        from_idx = self.from_col + self.from_row * 9
        to_idx = self.to_col + self.to_row * 9
        return from_idx + to_idx * 90

    @classmethod
    def decode(cls, encoded: int) -> "Move":
        """从编码解码着法"""
        to_idx = encoded // 90
        from_idx = encoded % 90
        return cls(
            from_col=from_idx % 9,
            from_row=from_idx // 9,
            to_col=to_idx % 9,
            to_row=to_idx // 9,
        )
