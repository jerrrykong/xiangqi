// Package log provides structured logging for the application.
package log

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

// Level represents log level
type Level int

const (
	LevelDebug Level = iota
	LevelInfo
	LevelWarn
	LevelError
	LevelFatal
)

func (l Level) String() string {
	switch l {
	case LevelDebug:
		return "DEBUG"
	case LevelInfo:
		return "INFO"
	case LevelWarn:
		return "WARN"
	case LevelError:
		return "ERROR"
	case LevelFatal:
		return "FATAL"
	default:
		return "UNKNOWN"
	}
}

// Logger is the global logger instance
type Logger struct {
	mu       sync.Mutex
	level    Level
	prefix   string
	flags    int
	output   *os.File
	timeFunc func() time.Time
}

var defaultLogger = &Logger{
	level:    LevelInfo,
	flags:    log.LstdFlags,
	timeFunc: time.Now,
}

// ContextKey is a type for context keys
type ContextKey string

const (
	// ContextKeyRequestID is the context key for request ID
	ContextKeyRequestID ContextKey = "request_id"
	// ContextKeyUserID is the context key for user ID
	ContextKeyUserID ContextKey = "user_id"
	// ContextKeyUsername is the context key for username
	ContextKeyUserName ContextKey = "username"
)

// Init initializes the global logger
// level: debug, info, warn, error
func Init(level string) {
	switch strings.ToLower(level) {
	case "debug":
		defaultLogger.level = LevelDebug
	case "info":
		defaultLogger.level = LevelInfo
	case "warn":
		defaultLogger.level = LevelWarn
	case "error":
		defaultLogger.level = LevelError
	default:
		defaultLogger.level = LevelInfo
	}
	log.SetOutput(os.Stdout)
}

// SetOutput sets the output destination for the logger
func SetOutput(w *os.File) {
	defaultLogger.mu.Lock()
	defer defaultLogger.mu.Unlock()
	defaultLogger.output = w
}

// WithRequestID adds request ID to the context
func WithRequestID(ctx context.Context, requestID string) context.Context {
	return context.WithValue(ctx, ContextKeyRequestID, requestID)
}

// GetRequestID retrieves request ID from context
func GetRequestID(ctx context.Context) string {
	if id := ctx.Value(ContextKeyRequestID); id != nil {
		return id.(string)
	}
	return ""
}

// WithUserID adds user ID to the context
func WithUserID(ctx context.Context, userID int64) context.Context {
	return context.WithValue(ctx, ContextKeyUserID, userID)
}

// GetUserID retrieves user ID from context
func GetUserID(ctx context.Context) int64 {
	if id := ctx.Value(ContextKeyUserID); id != nil {
		return id.(int64)
	}
	return 0
}

// WithUsername adds username to the context
func WithUsername(ctx context.Context, username string) context.Context {
	return context.WithValue(ctx, ContextKeyUserName, username)
}

// GetUsername retrieves username from context
func GetUsername(ctx context.Context) string {
	if name := ctx.Value(ContextKeyUserName); name != nil {
		return name.(string)
	}
	return ""
}

// formatFields formats key-value pairs for structured logging
func formatFields(fields ...any) string {
	if len(fields) == 0 {
		return ""
	}
	var parts []string
	for i := 0; i < len(fields); i += 2 {
		if i+1 < len(fields) {
			key, ok := fields[i].(string)
			if ok {
				parts = append(parts, fmt.Sprintf("%s=%v", key, fields[i+1]))
			}
		}
	}
	if len(parts) == 0 {
		return ""
	}
	return " " + strings.Join(parts, " ")
}

// log writes a log entry
func (l *Logger) log(level Level, msg string, fields ...any) {
	if level < l.level {
		return
	}

	l.mu.Lock()
	defer l.mu.Unlock()

	// Get caller info
	_, file, line, ok := runtime.Caller(2)
	caller := ""
	if ok {
		caller = fmt.Sprintf("%s:%d", filepath.Base(file), line)
	}

	// Format timestamp
	ts := l.timeFunc().Format("2006-01-02 15:04:05.000")

	// Build log line
	levelStr := level.String()
	if len(fields) > 0 {
		fieldStr := formatFields(fields...)
		log.Printf("[%s] %s %s %s |%s\n", levelStr, ts, caller, msg, fieldStr)
	} else {
		log.Printf("[%s] %s %s %s\n", levelStr, ts, caller, msg)
	}

	if level == LevelFatal {
		os.Exit(1)
	}
}

// ---- Convenience functions ----

// Debug logs a debug message
func Debug(msg string, fields ...any) {
	defaultLogger.log(LevelDebug, msg, fields...)
}

// Info logs an info message
func Info(msg string, fields ...any) {
	defaultLogger.log(LevelInfo, msg, fields...)
}

// Warn logs a warning message
func Warn(msg string, fields ...any) {
	defaultLogger.log(LevelWarn, msg, fields...)
}

// Error logs an error message
func Error(msg string, fields ...any) {
	defaultLogger.log(LevelError, msg, fields...)
}

// Fatal logs a fatal message and exits
func Fatal(msg string, fields ...any) {
	defaultLogger.log(LevelFatal, msg, fields...)
}

// ---- HTTP-specific logging helpers ----

// HTTPRequest logs HTTP request details
func HTTPRequest(method, path, clientIP string, status int, duration time.Duration, userID int64, err error) {
	fields := []any{
		"method", method,
		"path", path,
		"client_ip", clientIP,
		"status", status,
		"duration_ms", duration.Milliseconds(),
	}
	if userID > 0 {
		fields = append(fields, "user_id", userID)
	}
	if err != nil {
		fields = append(fields, "error", err.Error())
		defaultLogger.log(LevelError, "http_request", fields...)
	} else if status >= 500 {
		defaultLogger.log(LevelError, "http_request", fields...)
	} else if status >= 400 {
		defaultLogger.log(LevelWarn, "http_request", fields...)
	} else {
		defaultLogger.log(LevelInfo, "http_request", fields...)
	}
}

// JWTAuth logs JWT authentication events
func JWTAuth(success bool, username string, userID int64, reason string) {
	fields := []any{
		"success", success,
		"reason", reason,
	}
	if username != "" {
		fields = append(fields, "username", username)
	}
	if userID > 0 {
		fields = append(fields, "user_id", userID)
	}
	if success {
		defaultLogger.log(LevelInfo, "jwt_auth", fields...)
	} else {
		defaultLogger.log(LevelWarn, "jwt_auth", fields...)
	}
}

// DBQuery logs database query execution
func DBQuery(table string, operation string, duration time.Duration, err error) {
	fields := []any{
		"table", table,
		"operation", operation,
		"duration_ms", duration.Milliseconds(),
	}
	if err != nil {
		fields = append(fields, "error", err.Error())
		defaultLogger.log(LevelError, "db_query", fields...)
	} else {
		defaultLogger.log(LevelDebug, "db_query", fields...)
	}
}

// ---- Game-specific logging helpers ----

// GameRoomEvent logs game room events
func GameRoomEvent(roomID, event string, userID int64, fields ...any) {
	allFields := append([]any{
		"room_id", roomID,
		"event", event,
	}, fields...)
	if userID > 0 {
		allFields = append(allFields, "user_id", userID)
	}
	defaultLogger.log(LevelInfo, "game_room", allFields...)
}

// GameMove logs a game move
func GameMove(roomID string, side string, fromX, fromY, toX, toY int, valid bool) {
	defaultLogger.log(LevelInfo, "game_move",
		"room_id", roomID,
		"side", side,
		"from", fmt.Sprintf("%d,%d", fromX, fromY),
		"to", fmt.Sprintf("%d,%d", toX, toY),
		"valid", valid,
	)
}

// GameOver logs game over event
func GameOver(roomID, result, winner string, moveCount int, duration time.Duration) {
	defaultLogger.log(LevelInfo, "game_over",
		"room_id", roomID,
		"result", result,
		"winner", winner,
		"move_count", moveCount,
		"duration_seconds", int(duration.Seconds()),
	)
}

// WebSocketEvent logs WebSocket events
func WebSocketEvent(event, sessionID, roomID string, userID int64, fields ...any) {
	allFields := append([]any{
		"event", event,
		"session_id", sessionID,
	}, fields...)
	if roomID != "" {
		allFields = append(allFields, "room_id", roomID)
	}
	if userID > 0 {
		allFields = append(allFields, "user_id", userID)
	}
	defaultLogger.log(LevelInfo, "websocket", allFields...)
}

// ---- Service layer logging helpers ----

// ServiceCall logs service method calls
func ServiceCall(service, method string, fields ...any) {
	allFields := append([]any{"service", service, "method", method}, fields...)
	defaultLogger.log(LevelDebug, "service_call", allFields...)
}

// ServiceResult logs service method results
func ServiceResult(service, method string, duration time.Duration, err error) {
	fields := []any{
		"service", service,
		"method", method,
		"duration_ms", duration.Milliseconds(),
	}
	if err != nil {
		fields = append(fields, "error", err.Error())
		defaultLogger.log(LevelError, "service_result", fields...)
	} else {
		defaultLogger.log(LevelDebug, "service_result", fields...)
	}
}
