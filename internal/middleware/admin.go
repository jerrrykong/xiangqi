package middleware

import (
	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// AdminOnly creates a middleware that only allows admin users
func AdminOnly() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !IsAdmin(c) {
			response.Forbidden(c)
			c.Abort()
			return
		}
		c.Next()
	}
}
