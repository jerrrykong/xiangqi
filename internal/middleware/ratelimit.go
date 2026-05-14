package middleware

import (
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
)

// RateLimit creates a rate limiting middleware using Redis
func RateLimit(redisClient *redis.Client, maxReq int, window time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Use IP + path as the rate limit key
		key := fmt.Sprintf("ratelimit:%s:%s", c.ClientIP(), c.FullPath())

		ctx := c.Request.Context()

		// Increment the counter
		count, err := redisClient.Incr(ctx, key).Result()
		if err != nil {
			log.Error("ratelimit_redis_error",
				"path", c.Request.URL.Path,
				"client_ip", c.ClientIP(),
				"error", err.Error(),
			)
			// Redis error - allow the request through
			c.Next()
			return
		}

		// Set expiry on first request
		if count == 1 {
			redisClient.Expire(ctx, key, window)
		}

		// Check if limit exceeded
		if count > int64(maxReq) {
			log.Warn("ratelimit_exceeded",
				"path", c.Request.URL.Path,
				"client_ip", c.ClientIP(),
				"count", count,
				"limit", maxReq,
			)
			response.TooManyRequests(c)
			c.Abort()
			return
		}

		log.Debug("ratelimit_check",
			"path", c.Request.URL.Path,
			"client_ip", c.ClientIP(),
			"count", count,
			"limit", maxReq,
		)

		c.Next()
	}
}

// RateLimitByUser creates a rate limiting middleware that limits by user ID
func RateLimitByUser(redisClient *redis.Client, maxReq int, window time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := GetUserID(c)
		if userID == 0 {
			// No user ID - use IP based limiting
			RateLimit(redisClient, maxReq, window)(c)
			return
		}

		key := fmt.Sprintf("ratelimit:user:%d:%s", userID, c.FullPath())
		ctx := c.Request.Context()

		count, err := redisClient.Incr(ctx, key).Result()
		if err != nil {
			log.Error("ratelimit_redis_error",
				"path", c.Request.URL.Path,
				"user_id", userID,
				"error", err.Error(),
			)
			c.Next()
			return
		}

		if count == 1 {
			redisClient.Expire(ctx, key, window)
		}

		if count > int64(maxReq) {
			log.Warn("ratelimit_exceeded",
				"path", c.Request.URL.Path,
				"user_id", userID,
				"count", count,
				"limit", maxReq,
			)
			response.TooManyRequests(c)
			c.Abort()
			return
		}

		log.Debug("ratelimit_check",
			"path", c.Request.URL.Path,
			"user_id", userID,
			"count", count,
			"limit", maxReq,
		)

		c.Next()
	}
}
