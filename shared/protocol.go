// Package shared 包含跨服务共享的常量、错误码和协议定义
package shared

import "encoding/json"

// ============ HTTP 统一响应格式 ============

// Response HTTP 统一响应
type Response struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
}

// ErrorResponse 错误响应
type ErrorResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Detail  string `json:"detail,omitempty"`
}

// NewResponse 创建成功响应
func NewResponse(data interface{}) *Response {
	var raw json.RawMessage
	if data != nil {
		raw, _ = json.Marshal(data)
	}
	return &Response{
		Code:    0,
		Message: "ok",
		Data:    raw,
	}
}

// NewErrorResponse 创建错误响应
func NewErrorResponse(code int, message string, detail string) *ErrorResponse {
	return &ErrorResponse{
		Code:    code,
		Message: message,
		Detail:  detail,
	}
}

// ============ Move 着法结构 ============

// Move 着法
type Move struct {
	FromCol int `json:"from_col"` // 起始列 0-8
	FromRow int `json:"from_row"` // 起始行 0-9
	ToCol   int `json:"to_col"`   // 目标列 0-8
	ToRow   int `json:"to_row"`   // 目标行 0-9
}

// NewMove 创建新着法
func NewMove(fromCol, fromRow, toCol, toRow int) *Move {
	return &Move{
		FromCol: fromCol,
		FromRow: fromRow,
		ToCol:   toCol,
		ToRow:   toRow,
	}
}

// IsValid 检查着法坐标是否有效
func (m *Move) IsValid() bool {
	return m.FromCol >= 0 && m.FromCol < BoardCols &&
		m.FromRow >= 0 && m.FromRow < BoardRows &&
		m.ToCol >= 0 && m.ToCol < BoardCols &&
		m.ToRow >= 0 && m.ToRow < BoardRows
}

// Equal 检查两个着法是否相同
func (m *Move) Equal(other *Move) bool {
	return m.FromCol == other.FromCol &&
		m.FromRow == other.FromRow &&
		m.ToCol == other.ToCol &&
		m.ToRow == other.ToRow
}

// Encode 将着法编码为整数 (0-2084)
// 编码方式: encoded = from * 90 + to
func (m *Move) Encode() int {
	return m.FromCol + m.FromRow*BoardCols + (m.ToCol+m.ToRow*BoardCols)*BoardSize
}

// Decode 从编码解码着法
func DecodeMove(encoded int) *Move {
	to := encoded / BoardSize
	from := encoded % BoardSize
	return &Move{
		FromCol: from % BoardCols,
		FromRow: from / BoardCols,
		ToCol:   to % BoardCols,
		ToRow:   to / BoardCols,
	}
}

// ============ WebSocket 消息结构 ============

// WSMessage WebSocket 消息基类
type WSMessage struct {
	Type string `json:"type"`
}

// Client -> Server 消息

// MoveMessage 走棋消息
type MoveMessage struct {
	Type string `json:"type"`
	Move *Move  `json:"move"`
}

// ResignMessage 认输消息
type ResignMessage struct {
	Type string `json:"type"`
}

// DrawReqMessage 请求和棋消息
type DrawReqMessage struct {
	Type string `json:"type"`
}

// DrawAnsMessage 和棋应答消息
type DrawAnsMessage struct {
	Type  string `json:"type"`
	Accept bool `json:"accept"`
}

// PingMessage 心跳消息
type PingMessage struct {
	Type string `json:"type"`
	Time int64  `json:"time"`
}

// ReconnectMessage 重连消息
type ReconnectMessage struct {
	Type  string `json:"type"`
	Token string `json:"token"`
}

// Server -> Client 消息

// StateSyncMessage 状态同步消息
type StateSyncMessage struct {
	Type      string   `json:"type"`
	Board     [][]int `json:"board"`     // 10x9 棋盘数组
	Turn      int     `json:"turn"`      // 当前回合 (0=红, 1=黑)
	RedTime   int64   `json:"red_time"`  // 红方剩余时间(秒)
	BlackTime int64   `json:"black_time"`// 黑方剩余时间(秒)
	RoomID    string  `json:"room_id"`
	YourColor int     `json:"your_color"`// 你的颜色
}

// OpponentMoveMessage 对手走棋消息
type OpponentMoveMessage struct {
	Type      string `json:"type"`
	Move      *Move  `json:"move"`
	RedTime   int64  `json:"red_time"`
	BlackTime int64  `json:"black_time"`
}

// GameStartMessage 游戏开始消息
type GameStartMessage struct {
	Type      string `json:"type"`
	RoomID    string `json:"room_id"`
	YourColor int    `json:"your_color"`
	RedTime   int64  `json:"red_time"`
	BlackTime int64  `json:"black_time"`
}

// GameOverMessage 游戏结束消息
type GameOverMessage struct {
	Type   string `json:"type"`
	Result string `json:"result"`
	Reason string `json:"reason"`
	Winner int    `json:"winner"` // -1=无, 0=红, 1=黑
}

// CheckMessage 将军消息
type CheckMessage struct {
	Type     string `json:"type"`
	ByPiece  int    `json:"by_piece"`  // 将军棋子
	FromRow  int    `json:"from_row"`
	FromCol  int    `json:"from_col"`
	ToRow    int    `json:"to_row"`
	ToCol    int    `json:"to_col"`
}

// DrawNotifyMessage 和棋通知消息
type DrawNotifyMessage struct {
	Type  string `json:"type"`
	From  string `json:"from"`
	Token string `json:"token,omitempty"`
}

// ErrorMessage 错误消息
type ErrorMessage struct {
	Type    string `json:"type"`
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// PongMessage 心跳响应消息
type PongMessage struct {
	Type string `json:"type"`
	Time int64  `json:"time"`
}
