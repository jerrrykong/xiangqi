package middleware

import (
	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// AdminOnly creates a middleware that only allows admin users with logging
func AdminOnly() gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := GetUserID(c)
		username := GetUsername(c)

		if !IsAdmin(c) {
			log.Warn("admin_access_denied",
				"path", c.Request.URL.Path,
				"user_id", userID,
				"username", username,
			)
			response.Forbidden(c)
			c.Abort()
			return
		}

		log.Debug("admin_access_granted",
			"path", c.Request.URL.Path,
			"user_id", userID,
			"username", username,
		)

		c.Next()
	}
}
