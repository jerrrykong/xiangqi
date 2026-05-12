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
	ErrCodeSystem       = 1000 + iota // 系统错误
	ErrCodeInternal                   // 内部错误
	ErrCodeDatabase                   // 数据库错误
	ErrCodeRedis                      // Redis 错误
	ErrCodeInvalidParam               // 参数错误
)

// 2xxx: 认证错误
const (
	ErrCodeAuth        = 2000 + iota // 认证错误
	ErrCodeUnauthorized              // 未认证
	ErrCodeTokenExpired              // Token 过期
	ErrCodeTokenInvalid              // Token 无效
	ErrCodeWrongPassword             // 密码错误
	ErrCodeUserNotFound              // 用户不存在
	ErrCodeUserExists                // 用户已存在
)

// 3xxx: 房间错误
const (
	ErrCodeRoom        = 3000 + iota // 房间错误
	ErrCodeRoomNotFound             // 房间不存在
	ErrCodeRoomFull                 // 房间已满
	ErrCodeRoomNotStarted           // 对局未开始
	ErrCodeRoomAlreadyStarted       // 对局已开始
	ErrCodeNotRoomOwner             // 非房主
	ErrCodeNotYourTurn              // 非你的回合
	ErrCodeAlreadyReady             // 已准备
	ErrCodeNotReady                 // 未准备
)

// 4xxx: 游戏错误
const (
	ErrCodeGame        = 4000 + iota // 游戏错误
	ErrCodeInvalidMove               // 无效着法
	ErrCodeMoveNotYourTurn           // 顺序错误
	ErrCodeGameNotStarted            // 游戏未开始
	ErrCodeGameAlreadyOver           // 游戏已结束
	ErrCodeCheck                     // 将军
)
