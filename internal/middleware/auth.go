// Package middleware provides Gin middleware implementations
package middleware

import (
	"strings"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/jwt"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// ContextKey is a type for context keys
type ContextKey string

const (
	// ContextKeyUserID is the context key for user ID
	ContextKeyUserID ContextKey = "user_id"
	// ContextKeyUsername is the context key for username
	ContextKeyUsername ContextKey = "username"
	// ContextKeyIsAdmin is the context key for admin status
	ContextKeyIsAdmin ContextKey = "is_admin"
)

// JWTAuth creates a JWT authentication middleware
func JWTAuth(jwtManager *jwt.JWTManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			response.Unauthorized(c)
			c.Abort()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			response.UnauthorizedWithMessage(c, "invalid token format")
			c.Abort()
			return
		}

		tokenString := parts[1]
		claims, err := jwtManager.ParseToken(tokenString)
		if err != nil {
			if err == jwt.ErrTokenExpired {
				response.TokenExpired(c)
			} else {
				response.TokenInvalid(c)
			}
			c.Abort()
			return
		}

		// Set user context
		c.Set(string(ContextKeyUserID), claims.UserID)
		c.Set(string(ContextKeyUsername), claims.Username)
		c.Set(string(ContextKeyIsAdmin), claims.IsAdmin)

		c.Next()
	}
}

// GetUserID extracts user ID from context
func GetUserID(c *gin.Context) int64 {
	if userID, exists := c.Get(string(ContextKeyUserID)); exists {
		return userID.(int64)
	}
	return 0
}

// GetUsername extracts username from context
func GetUsername(c *gin.Context) string {
	if username, exists := c.Get(string(ContextKeyUsername)); exists {
		return username.(string)
	}
	return ""
}

// IsAdmin checks if the current user is an admin
func IsAdmin(c *gin.Context) bool {
	if isAdmin, exists := c.Get(string(ContextKeyIsAdmin)); exists {
		return isAdmin.(bool)
	}
	return false
}
