// Package response provides unified HTTP response formatting
package response

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/shared"
)

// Response represents the standard API response
type Response struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// OK sends a success response with data
func OK(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, Response{Code: 0, Message: "ok", Data: data})
}

// OKWithCode sends a success response with custom code
func OKWithCode(c *gin.Context, code int, message string, data interface{}) {
	c.JSON(http.StatusOK, Response{Code: code, Message: message, Data: data})
}

// Fail sends a failure response
func Fail(c *gin.Context, httpStatus int, code int, message string) {
	c.JSON(httpStatus, Response{Code: code, Message: message, Data: nil})
}

// FailWithData sends a failure response with data
func FailWithData(c *gin.Context, httpStatus int, code int, message string, data interface{}) {
	c.JSON(httpStatus, Response{Code: code, Message: message, Data: data})
}

// BadRequest sends a 400 Bad Request response
func BadRequest(c *gin.Context, message string) {
	Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, message)
}

// Unauthorized sends a 401 Unauthorized response
func Unauthorized(c *gin.Context) {
	Fail(c, http.StatusUnauthorized, shared.ErrCodeUnauthorized, "unauthorized")
}

// UnauthorizedWithMessage sends a 401 Unauthorized response with custom message
func UnauthorizedWithMessage(c *gin.Context, message string) {
	Fail(c, http.StatusUnauthorized, shared.ErrCodeUnauthorized, message)
}

// TokenExpired sends a 401 response for expired token
func TokenExpired(c *gin.Context) {
	Fail(c, http.StatusUnauthorized, shared.ErrCodeTokenExpired, "token expired")
}

// TokenInvalid sends a 401 response for invalid token
func TokenInvalid(c *gin.Context) {
	Fail(c, http.StatusUnauthorized, shared.ErrCodeTokenInvalid, "token invalid")
}

// Forbidden sends a 403 Forbidden response
func Forbidden(c *gin.Context) {
	Fail(c, http.StatusForbidden, shared.ErrCodeAuth, "forbidden")
}

// NotFound sends a 404 Not Found response
func NotFound(c *gin.Context, message string) {
	Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, message)
}

// Conflict sends a 409 Conflict response
func Conflict(c *gin.Context, code int, message string) {
	Fail(c, http.StatusConflict, code, message)
}

// TooManyRequests sends a 429 Too Many Requests response
func TooManyRequests(c *gin.Context) {
	Fail(c, http.StatusTooManyRequests, shared.ErrCodeRateLimit, "rate limit exceeded")
}

// InternalError sends a 500 Internal Server Error response
func InternalError(c *gin.Context) {
	Fail(c, http.StatusInternalServerError, shared.ErrCodeSystem, "system error")
}

// ServiceUnavailable sends a 503 Service Unavailable response
func ServiceUnavailable(c *gin.Context) {
	Fail(c, http.StatusServiceUnavailable, shared.ErrCodeInternal, "service unavailable")
}
