package middleware

import (
	"time"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// Logger creates a logging middleware with structured logging
func Logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method
		clientIP := c.ClientIP()

		// Get user ID if authenticated
		userID := GetUserID(c)

		// Process request
		c.Next()

		// Calculate latency
		latency := time.Since(start)
		status := c.Writer.Status()

		// Log with structured fields
		log.HTTPRequest(method, path, clientIP, status, latency, userID, nil)

		// Log any errors
		if len(c.Errors) > 0 {
			for _, e := range c.Errors {
				log.Error("handler_error",
					"path", path,
					"error", e.Error(),
				)
			}
		}
	}
}

// Recovery creates a recovery middleware that handles panics with logging
func Recovery() gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				log.Error("panic_recovered",
					"path", c.Request.URL.Path,
					"method", c.Request.Method,
					"client_ip", c.ClientIP(),
					"panic", err,
				)
				response.InternalError(c)
				c.Abort()
			}
		}()
		c.Next()
	}
}

// CORS creates a CORS middleware
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With, X-Internal-Key")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, PATCH, DELETE")

		if c.Request.Method == "OPTIONS" {
			log.Debug("cors_preflight",
				"path", c.Request.URL.Path,
				"client_ip", c.ClientIP(),
			)
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}
