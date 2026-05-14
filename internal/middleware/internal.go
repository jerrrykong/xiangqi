package middleware

import (
	"crypto/subtle"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// InternalAuth creates a middleware for internal service authentication with logging
func InternalAuth(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		key := c.GetHeader("X-Internal-Key")
		clientIP := c.ClientIP()
		path := c.Request.URL.Path

		if key == "" {
			log.Warn("internal_auth_failed",
				"path", path,
				"client_ip", clientIP,
				"reason", "missing_key",
			)
			response.Unauthorized(c)
			c.Abort()
			return
		}

		// Use constant-time comparison to prevent timing attacks
		if subtle.ConstantTimeCompare([]byte(key), []byte(secret)) != 1 {
			log.Warn("internal_auth_failed",
				"path", path,
				"client_ip", clientIP,
				"reason", "invalid_key",
			)
			response.Unauthorized(c)
			c.Abort()
			return
		}

		log.Debug("internal_auth_success",
			"path", path,
			"client_ip", clientIP,
		)

		c.Next()
	}
}
