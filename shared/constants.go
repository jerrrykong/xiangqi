// Package shared 包含跨服务共享的常量、错误码和协议定义
package shared

// ============ 棋子编码 ============
// 棋子编码: encoded = color * 10 + piece_type
// 红方 color = 0, 黑方 color = 1

const (
	// Piece encoding constants
	PieceEmpty  = -1
	PieceRedKing     = 0   // 将
	PieceRedAdvisor  = 1   // 士
	PieceRedBishop   = 2   // 相
	PieceRedKnight   = 3   // 马
	PieceRedRook     = 4   // 车
	PieceRedCannon   = 5   // 炮
	PieceRedPawn     = 6   // 兵
	PieceBlackKing   = 10  // 帅
	PieceBlackAdvisor = 11 // 仕
	PieceBlackBishop = 12  // 象
	PieceBlackKnight = 13  // 马
	PieceBlackRook   = 14  // 车
	PieceBlackCannon = 15  // 炮
	PieceBlackPawn   = 16  // 卒
)

// Color constants
const (
	ColorRed   = 0
	ColorBlack = 1
	ColorNone  = -1
)

// PieceType constants (for bitwise operations)
const (
	TypeKing    = 0
	TypeAdvisor = 1
	TypeBishop  = 2
	TypeKnight  = 3
	TypeRook    = 4
	TypeCannon  = 5
	TypePawn    = 6
)

// ============ 棋盘常量 ============
// 棋盘: 10行 × 9列
// 坐标: 列 a-i (0-8), 行 0-9 (0为红方底线)

// Board dimensions
const (
	BoardRows    = 10
	BoardCols    = 9
	BoardSize    = BoardRows * BoardCols
	RedPalaceTop    = 7  // 红方九宫顶行
	RedPalaceBottom = 9  // 红方九宫底行
	RedPalaceLeft   = 3  // 红方九宫左列
	RedPalaceRight  = 5  // 红方九宫右列
	BlackPalaceTop    = 0 // 黑方九宫顶行
	BlackPalaceBottom = 2 // 黑方九宫底行
	BlackPalaceLeft   = 3 // 黑方九宫左列
	BlackPalaceRight  = 5 // 黑方九宫右列
	RiverRow = 4  // 楚河汉界所在行
)

// ============ 难度等级 ============
const (
	DifficultyEasy     = 1  // 简单:   100 次 MCTS 模拟
	DifficultyMedium   = 2  // 中等:   400 次 MCTS 模拟
	DifficultyHard     = 3  // 困难:   800 次 MCTS 模拟
	DifficultyExpert   = 4  // 大师:   1600 次 MCTS 模拟
	DifficultyMaster   = 5  // 宗师:   3200+ 次 MCTS 模拟
)

// Difficulty simulation counts
var DifficultySimulations = map[int]int{
	DifficultyEasy:   100,
	DifficultyMedium:  400,
	DifficultyHard:    800,
	DifficultyExpert: 1600,
	DifficultyMaster: 3200,
}

// ============ 房间状态 ============
const (
	RoomStatusWaiting  = "waiting"  // 等待玩家
	RoomStatusReady    = "ready"   // 玩家已就绪
	RoomStatusPlaying  = "playing" // 对局中
	RoomStatusFinished = "finished" // 对局结束
)

// ============ 房间类型 ============
const (
	RoomTypePVP = "pvp"  // 人人对战
	RoomTypePVE = "pve"  // 人机对战
)

// ============ 游戏结果 ============
const (
	ResultRedWins     = "RED_WINS"
	ResultBlackWins   = "BLACK_WINS"
	ResultDraw        = "DRAW"
	ResultRedResign   = "RED_RESIGN"
	ResultBlackResign = "BLACK_RESIGN"
	ResultRedTimeout  = "RED_TIMEOUT"
	ResultBlackTimeout = "BLACK_TIMEOUT"
)

// ============ 胜负原因 ============
const (
	ReasonCheckmate    = "CHECKMATE"    // 将死
	ReasonStalemate    = "STALEMATE"   // 困毙
	ReasonResign       = "RESIGN"      // 认输
	ReasonTimeout      = "TIMEOUT"      // 超时
	ReasonAgreement    = "AGREEMENT"    // 双方同意
	ReasonFiftyMove    = "FIFTY_MOVE"   // 50回合和棋
)

// ============ 着法编码 ============
// 标准象棋着法编码范围: 0-2084
const (
	MoveEncodingBase   = BoardCols * BoardRows  // 90
	MaxMoveEncoding    = MoveEncodingBase * MoveEncodingBase // 8100
)

// ============ WebSocket 消息类型 ============
const (
	// Client -> Server
	MsgTypeMove      = "move"
	MsgTypeResign    = "resign"
	MsgTypeDrawReq   = "draw_req"
	MsgTypeDrawAns   = "draw_ans"
	MsgTypePing      = "ping"
	MsgTypeReconnect = "reconnect"

	// Server -> Client
	MsgTypeStateSync  = "state_sync"
	MsgTypeOpponentMove = "opponent_move"
	MsgTypeGameStart  = "game_start"
	MsgTypeGameOver   = "game_over"
	MsgTypeCheck      = "check"
	MsgTypeDrawNotify = "draw_notify"
	MsgTypeError      = "error"
	MsgTypePong       = "pong"
)

// ============ 错误码 ============
// 1xxx: 系统错误
const (
	ErrCodeSystem       = 1000
	ErrCodeInternal     = 1001
	ErrCodeDatabase     = 1002
	ErrCodeRedis        = 1003
	ErrCodeInvalidParam = 1004
	ErrCodeRateLimit    = 1005
)

// 2xxx: 认证错误
const (
	ErrCodeAuth           = 2000
	ErrCodeUnauthorized   = 2001
	ErrCodeTokenExpired   = 2002
	ErrCodeTokenInvalid   = 2003
	ErrCodeWrongPassword  = 2004
	ErrCodeUserNotFound   = 2005
	ErrCodeUserExists     = 2006
	ErrCodeUserBanned     = 2007
)

// 3xxx: 房间错误
const (
	ErrCodeRoom             = 3000
	ErrCodeRoomNotFound     = 3001
	ErrCodeRoomFull         = 3002
	ErrCodeRoomNotWaiting   = 3003
	ErrCodeAlreadyInRoom    = 3004
	ErrCodeNotInRoom        = 3005
	ErrCodeRoomNotStarted   = 3006
	ErrCodeRoomAlreadyStarted = 3007
	ErrCodeNotRoomOwner       = 3008
	ErrCodeOpponentNotReady     = 3009
	ErrCodeMatchTimeout         = 3010
)

// 4xxx: 游戏错误
const (
	ErrCodeGame           = 4000
	ErrCodeInvalidMove    = 4001
	ErrCodeMoveNotYourTurn = 4002
	ErrCodeGameNotStarted = 4003
	ErrCodeGameAlreadyOver = 4004
	ErrCodeCheck          = 4005
	ErrCodeReconnectFailed = 4006
	ErrCodeNotYourTurn    = 4007
	ErrCodeAlreadyReady   = 4008
	ErrCodeNotReady      = 4009
)
