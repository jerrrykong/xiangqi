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
