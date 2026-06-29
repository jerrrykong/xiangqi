// 象棋相关类型定义

// 棋子编码 (与后端 shared/constants.go 保持一致)
// color * 10 + piece_type
export const Piece = {
  Empty: -1,
  // 红方
  RedKing: 0,      // 将
  RedAdvisor: 1,   // 士
  RedBishop: 2,    // 相
  RedKnight: 3,    // 马
  RedRook: 4,     // 车
  RedCannon: 5,    // 炮
  RedPawn: 6,      // 兵
  // 黑方
  BlackKing: 10,   // 帅
  BlackAdvisor: 11, // 仕
  BlackBishop: 12,  // 象
  BlackKnight: 13,  // 马
  BlackRook: 14,    // 车
  BlackCannon: 15,  // 炮
  BlackPawn: 16,    // 卒
} as const

export type PieceType = typeof Piece[keyof typeof Piece]

// 颜色常量
export const Color = {
  Red: 0,
  Black: 1,
  None: -1,
} as const

export type ColorType = typeof Color[keyof typeof Color]

// 棋盘尺寸
export const BoardConfig = {
  Rows: 10,
  Cols: 9,
  Size: 90, // 10 * 9
  // 九宫范围
  RedPalaceTop: 7,
  RedPalaceBottom: 9,
  RedPalaceLeft: 3,
  RedPalaceRight: 5,
  BlackPalaceTop: 0,
  BlackPalaceBottom: 2,
  BlackPalaceLeft: 3,
  BlackPalaceRight: 5,
  // 楚河汉界
  RiverRow: 4,
} as const

// 棋子显示字符
export const PieceChars: Partial<Record<PieceType, string>> = {
  [Piece.RedKing]: '帥',
  [Piece.RedAdvisor]: '仕',
  [Piece.RedBishop]: '相',
  [Piece.RedKnight]: '馬',
  [Piece.RedRook]: '車',
  [Piece.RedCannon]: '炮',
  [Piece.RedPawn]: '兵',
  [Piece.BlackKing]: '將',
  [Piece.BlackAdvisor]: '仕',
  [Piece.BlackBishop]: '象',
  [Piece.BlackKnight]: '馬',
  [Piece.BlackRook]: '車',
  [Piece.BlackCannon]: '炮',
  [Piece.BlackPawn]: '卒',
}

// 棋子名称
export const PieceNames: Partial<Record<PieceType, string>> = {
  [Piece.RedKing]: '帅',
  [Piece.RedAdvisor]: '士',
  [Piece.RedBishop]: '相',
  [Piece.RedKnight]: '马',
  [Piece.RedRook]: '车',
  [Piece.RedCannon]: '炮',
  [Piece.RedPawn]: '兵',
  [Piece.BlackKing]: '将',
  [Piece.BlackAdvisor]: '士',
  [Piece.BlackBishop]: '象',
  [Piece.BlackKnight]: '马',
  [Piece.BlackRook]: '车',
  [Piece.BlackCannon]: '炮',
  [Piece.BlackPawn]: '卒',
}

// 棋子类型判断
export function getPieceColor(piece: PieceType): ColorType {
  if (piece < 0) return Color.None
  return Math.floor(piece / 10) as ColorType
}

export function isRedPiece(piece: PieceType): boolean {
  return piece >= 0 && piece < 10
}

export function isBlackPiece(piece: PieceType): boolean {
  return piece >= 10 && piece < 20
}

// 棋子尺寸
export const PieceConfig = {
  Size: 50, // 棋子直径
  FontSize: 28, // 棋子字体大小
} as const

// 棋盘坐标
export interface Position {
  col: number // 0-8
  row: number // 0-9
}

// 着法
export interface Move {
  from_col: number
  from_row: number
  to_col: number
  to_row: number
}

// v2.0 协议格式转换: Move → from_pos/to_pos
export function moveToPos(move: Move): { from_pos: number[]; to_pos: number[] } {
  return {
    from_pos: [move.from_row, move.from_col],
    to_pos: [move.to_row, move.to_col],
  }
}

// v2.0 协议格式转换: from_pos/to_pos → Move
export function posToMove(fromPos: number[], toPos: number[]): Move {
  return {
    from_row: fromPos[0],
    from_col: fromPos[1],
    to_row: toPos[0],
    to_col: toPos[1],
  }
}

// 初始棋盘布局
export function getInitialBoard(): number[][] {
  // 棋盘: 10行 x 9列
  // row 0: 黑方底线
  // row 4: 楚河汉界
  // row 9: 红方底线
  return [
    // row 0 - 黑方底线
    [Piece.BlackRook, Piece.BlackKnight, Piece.BlackBishop, Piece.BlackAdvisor, Piece.BlackKing,
     Piece.BlackAdvisor, Piece.BlackBishop, Piece.BlackKnight, Piece.BlackRook],
    // row 1
    [Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty],
    // row 2
    [Piece.Empty, Piece.BlackCannon, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.BlackCannon, Piece.Empty],
    // row 3
    [Piece.BlackPawn, Piece.Empty, Piece.BlackPawn, Piece.Empty, Piece.BlackPawn, Piece.Empty, Piece.BlackPawn, Piece.Empty, Piece.BlackPawn],
    // row 4 - 楚河汉界
    [Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty],
    // row 5 - 楚河汉界
    [Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty],
    // row 6
    [Piece.RedPawn, Piece.Empty, Piece.RedPawn, Piece.Empty, Piece.RedPawn, Piece.Empty, Piece.RedPawn, Piece.Empty, Piece.RedPawn],
    // row 7
    [Piece.Empty, Piece.RedCannon, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.RedCannon, Piece.Empty],
    // row 8
    [Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty, Piece.Empty],
    // row 9 - 红方底线
    [Piece.RedRook, Piece.RedKnight, Piece.RedBishop, Piece.RedAdvisor, Piece.RedKing,
     Piece.RedAdvisor, Piece.RedBishop, Piece.RedKnight, Piece.RedRook],
  ]
}

// 游戏结果
export const GameResult = {
  RedWins: 'RED_WINS',
  BlackWins: 'BLACK_WINS',
  Draw: 'DRAW',
  RedResign: 'RED_RESIGN',
  BlackResign: 'BLACK_RESIGN',
  RedTimeout: 'RED_TIMEOUT',
  BlackTimeout: 'BLACK_TIMEOUT',
} as const

export type GameResultType = typeof GameResult[keyof typeof GameResult]

// 胜负原因
export const GameReason = {
  Checkmate: 'CHECKMATE',
  Stalemate: 'STALEMATE',
  Resign: 'RESIGN',
  Timeout: 'TIMEOUT',
  Agreement: 'AGREEMENT',
  FiftyMove: 'FIFTY_MOVE',
} as const

export type GameReasonType = typeof GameReason[keyof typeof GameReason]

// FEN 解析: 从 FEN 字符串恢复棋盘
const FEN_PIECE_MAP_UPPER: Record<string, number> = {
  K: Piece.RedKing,
  A: Piece.RedAdvisor,
  B: Piece.RedBishop,
  N: Piece.RedKnight,
  R: Piece.RedRook,
  C: Piece.RedCannon,
  P: Piece.RedPawn,
}
const FEN_PIECE_MAP_LOWER: Record<string, number> = {
  k: Piece.BlackKing,
  a: Piece.BlackAdvisor,
  b: Piece.BlackBishop,
  n: Piece.BlackKnight,
  r: Piece.BlackRook,
  c: Piece.BlackCannon,
  p: Piece.BlackPawn,
}

export function parseFEN(fen: string): number[][] {
  const boardPart = fen.includes(' ') ? fen.split(' ')[0] : fen
  const rows = boardPart.split('/')
  const board: number[][] = []

  for (let i = 0; i < rows.length; i++) {
    const row: number[] = []
    const rowStr = rows[i]
    for (const ch of rowStr) {
      if (ch >= '1' && ch <= '9') {
        for (let j = 0; j < parseInt(ch); j++) {
          row.push(Piece.Empty)
        }
      } else if (ch >= 'A' && ch <= 'Z') {
        row.push(FEN_PIECE_MAP_UPPER[ch] ?? Piece.Empty)
      } else if (ch >= 'a' && ch <= 'z') {
        row.push(FEN_PIECE_MAP_LOWER[ch] ?? Piece.Empty)
      }
    }
    board.push(row)
  }

  // FEN rows go from top (row 0 in our board = black side) to bottom (row 9 = red side)
  // But FEN writes from rank 10 (top) to rank 1 (bottom)
  // Our board[0] = row 0 (black side), board[9] = row 9 (red side)
  // FEN rows[0] = top of board = row 0, so the order matches
  return board
}

// ========== CRC32 & Board Hash ==========

// Pre-computed CRC32 lookup table (matching Python zlib.crc32)
const CRC_TABLE: number[] = []
;(function initCRC32Table() {
  for (let i = 0; i < 256; i++) {
    let crc = i
    for (let j = 0; j < 8; j++) {
      crc = (crc & 1) ? (0xEDB88320 ^ (crc >>> 1)) : (crc >>> 1)
    }
    CRC_TABLE[i] = crc >>> 0  // ensure unsigned
  }
})()

/**
 * Compute CRC32 of a UTF-8 string (matches Python zlib.crc32).
 * Returns unsigned 32-bit integer.
 */
function crc32(s: string): number {
  let crc = 0xFFFFFFFF
  const encoder = new TextEncoder()
  const bytes = encoder.encode(s)
  for (let i = 0; i < bytes.length; i++) {
    const tableIdx = (crc ^ bytes[i]) & 0xFF
    crc = (crc >>> 8) ^ CRC_TABLE[tableIdx]
  }
  return (crc ^ 0xFFFFFFFF) >>> 0
}

/** FEN piece chars: uppercase=Red, lowercase=Black. Index = piece % 10. */
const FEN_PIECE_CHARS = ['k', 'a', 'b', 'n', 'r', 'c', 'p']

/**
 * Convert board array to FEN string.
 * Must produce the same FEN as Python board_to_fen() for hash consistency.
 *
 * @param board 10×9 board array (row 0 = black side top, row 9 = red side bottom)
 * @param currentTurn 0 = Red, 1 = Black
 */
export function boardToFen(board: number[][], currentTurn: number): string {
  const lines: string[] = []
  for (let row = 0; row < 10; row++) {
    let line = ''
    let emptyCount = 0
    for (let col = 0; col < 9; col++) {
      const piece = board[row][col]
      if (piece < 0) {
        emptyCount++
      } else {
        if (emptyCount > 0) {
          line += emptyCount.toString()
          emptyCount = 0
        }
        const ptype = piece % 10           // 0=King..6=Pawn
        const isRed = piece < 10           // Red pieces: 0-6, Black: 10-16
        const ch = FEN_PIECE_CHARS[ptype]  // 'k'/'a'/'b'/'n'/'r'/'c'/'p'
        line += isRed ? ch.toUpperCase() : ch
      }
    }
    if (emptyCount > 0) {
      line += emptyCount.toString()
    }
    lines.push(line)
  }
  const turnChar = currentTurn === 0 ? 'r' : 'b'
  return lines.join('/') + ` ${turnChar} - - 0 1`
}

/**
 * Compute CRC32 hash of the current board state (via FEN).
 * Must match Python compute_board_hash() for server-side verification.
 *
 * @param board 10×9 board array
 * @param currentTurn 0 = Red, 1 = Black
 */
export function computeBoardHash(board: number[][], currentTurn: number): number {
  const fen = boardToFen(board, currentTurn)
  return crc32(fen)
}
