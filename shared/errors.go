// Package shared 包含跨服务共享的常量、错误码和协议定义
package shared

import "fmt"

// XiangqiError 象棋游戏错误类型
type XiangqiError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Detail  string `json:"detail,omitempty"`
}

func (e *XiangqiError) Error() string {
	if e.Detail != "" {
		return fmt.Sprintf("[%d] %s: %s", e.Code, e.Message, e.Detail)
	}
	return fmt.Sprintf("[%d] %s", e.Code, e.Message)
}

// NewError 创建新错误
func NewError(code int, message string, detail string) *XiangqiError {
	return &XiangqiError{
		Code:    code,
		Message: message,
		Detail:  detail,
	}
}

// Common errors
var (
	ErrSystem       = NewError(ErrCodeSystem, "系统错误", "")
	ErrInternal     = NewError(ErrCodeInternal, "内部错误", "")
	ErrDatabase     = NewError(ErrCodeDatabase, "数据库错误", "")
	ErrRedis        = NewError(ErrCodeRedis, "Redis 错误", "")
	ErrInvalidParam = NewError(ErrCodeInvalidParam, "参数错误", "")

	ErrUnauthorized   = NewError(ErrCodeUnauthorized, "未认证", "")
	ErrTokenExpired   = NewError(ErrCodeTokenExpired, "Token 已过期", "")
	ErrTokenInvalid   = NewError(ErrCodeTokenInvalid, "无效的 Token", "")
	ErrWrongPassword  = NewError(ErrCodeWrongPassword, "密码错误", "")
	ErrUserNotFound   = NewError(ErrCodeUserNotFound, "用户不存在", "")
	ErrUserExists     = NewError(ErrCodeUserExists, "用户已存在", "")

	ErrRoomNotFound      = NewError(ErrCodeRoomNotFound, "房间不存在", "")
	ErrRoomFull         = NewError(ErrCodeRoomFull, "房间已满", "")
	ErrRoomNotStarted   = NewError(ErrCodeRoomNotStarted, "对局未开始", "")
	ErrRoomAlreadyStarted = NewError(ErrCodeRoomAlreadyStarted, "对局已开始", "")
	ErrNotRoomOwner     = NewError(ErrCodeNotRoomOwner, "非房主", "")
	ErrNotInRoom        = NewError(ErrCodeNotInRoom, "不在任何房间", "")
	ErrNotYourTurn      = NewError(ErrCodeNotYourTurn, "非你的回合", "")
	ErrAlreadyReady     = NewError(ErrCodeAlreadyReady, "已准备", "")
	ErrNotReady         = NewError(ErrCodeNotReady, "未准备", "")
	ErrUserBanned       = NewError(ErrCodeUserBanned, "用户已被封禁", "")

	ErrInvalidMove       = NewError(ErrCodeInvalidMove, "无效着法", "")
	ErrMoveNotYourTurn   = NewError(ErrCodeMoveNotYourTurn, "顺序错误", "")
	ErrGameNotStarted    = NewError(ErrCodeGameNotStarted, "游戏未开始", "")
	ErrGameAlreadyOver   = NewError(ErrCodeGameAlreadyOver, "游戏已结束", "")
	ErrCheck             = NewError(ErrCodeCheck, "将军", "")
)

// ErrorCodeFromString 根据错误码字符串返回错误
func ErrorCodeFromString(codeStr string) *XiangqiError {
	switch codeStr {
	case "SYSTEM":
		return ErrSystem
	case "INTERNAL":
		return ErrInternal
	case "UNAUTHORIZED":
		return ErrUnauthorized
	case "TOKEN_EXPIRED":
		return ErrTokenExpired
	case "TOKEN_INVALID":
		return ErrTokenInvalid
	case "WRONG_PASSWORD":
		return ErrWrongPassword
	case "USER_NOT_FOUND":
		return ErrUserNotFound
	case "USER_EXISTS":
		return ErrUserExists
	case "ROOM_NOT_FOUND":
		return ErrRoomNotFound
	case "ROOM_FULL":
		return ErrRoomFull
	case "INVALID_MOVE":
		return ErrInvalidMove
	case "NOT_YOUR_TURN":
		return ErrNotYourTurn
	default:
		return NewError(ErrCodeSystem, "未知错误", codeStr)
	}
}
