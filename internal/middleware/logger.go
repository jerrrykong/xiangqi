package middleware

import (
	"log"
	"time"

	"github.com/gin-gonic/gin"
)

// Logger creates a logging middleware
func Logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()
		clientIP := c.ClientIP()

		log.Printf("[%s] %s %s %d %v %s",
			method,
			path,
			clientIP,
			status,
			latency,
			c.Errors.ByType(gin.ErrorTypePrivate).String(),
		)
	}
}

// Recovery creates a recovery middleware that handles panics
func Recovery() gin.HandlerFunc {
	return gin.Recovery()
}

// CORS creates a CORS middleware
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With, X-Internal-Key")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, PATCH, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}
