package middleware

import (
	"crypto/subtle"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// InternalAuth creates a middleware for internal service authentication
func InternalAuth(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		key := c.GetHeader("X-Internal-Key")
		if key == "" {
			response.Unauthorized(c)
			c.Abort()
			return
		}

		// Use constant-time comparison to prevent timing attacks
		if subtle.ConstantTimeCompare([]byte(key), []byte(secret)) != 1 {
			response.Unauthorized(c)
			c.Abort()
			return
		}

		c.Next()
	}
}
