package handler

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/middleware"
	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
	"github.com/jerrykong/xiangqi/internal/service"
	"github.com/jerrykong/xiangqi/shared"
)

// UserHandler handles user-related endpoints
type UserHandler struct {
	userSvc *service.UserService
}

// NewUserHandler creates a new UserHandler
func NewUserHandler(userSvc *service.UserService) *UserHandler {
	return &UserHandler{userSvc: userSvc}
}

// GetMe returns the current user's profile
// GET /users/me
func (h *UserHandler) GetMe(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)

	log.Debug("handler_get_me",
		"user_id", userID,
	)

	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		log.Error("handler_get_me_error",
			"user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_get_me_success",
		"user_id", userID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, profile)
}

// UpdateProfile updates the current user's profile
// PATCH /users/me
func (h *UserHandler) UpdateProfile(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)

	log.Debug("handler_update_profile_start",
		"user_id", userID,
	)

	var req service.UpdateProfileRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Warn("handler_update_profile_bad_request",
			"user_id", userID,
			"error", err.Error(),
		)
		response.BadRequest(c, "invalid request body")
		return
	}

	if err := h.userSvc.UpdateProfile(c.Request.Context(), userID, &req); err != nil {
		log.Error("handler_update_profile_error",
			"user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	// Return updated profile
	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		log.Error("handler_update_profile_get_user_error",
			"user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_update_profile_success",
		"user_id", userID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, profile)
}

// GetRankings returns the rankings
// GET /users/rankings
func (h *UserHandler) GetRankings(c *gin.Context) {
	start := time.Now()
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	log.Debug("handler_get_rankings",
		"page", page,
		"page_size", pageSize,
	)

	resp, err := h.userSvc.GetRankings(c.Request.Context(), &service.RankingsRequest{
		Page:     page,
		PageSize: pageSize,
	})
	if err != nil {
		log.Error("handler_get_rankings_error",
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_get_rankings_success",
		"total", resp.Total,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// GetHistory returns a user's game history
// GET /users/:id/history
func (h *UserHandler) GetHistory(c *gin.Context) {
	start := time.Now()
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		log.Warn("handler_get_history_bad_request",
			"user_id_str", userIDStr,
			"error", err.Error(),
		)
		response.BadRequest(c, "invalid user ID")
		return
	}

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	gameType := c.DefaultQuery("type", "")

	log.Debug("handler_get_history",
		"target_user_id", userID,
		"page", page,
		"page_size", pageSize,
		"type", gameType,
	)

	resp, err := h.userSvc.GetHistory(c.Request.Context(), userID, &service.HistoryRequest{
		Page:     page,
		PageSize: pageSize,
		Type:     gameType,
	})
	if err != nil {
		log.Error("handler_get_history_error",
			"target_user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_get_history_success",
		"target_user_id", userID,
		"total", resp.Total,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// GetUser returns a specific user's profile
// GET /users/:id
func (h *UserHandler) GetUser(c *gin.Context) {
	start := time.Now()
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		log.Warn("handler_get_user_bad_request",
			"user_id_str", userIDStr,
			"error", err.Error(),
		)
		response.BadRequest(c, "invalid user ID")
		return
	}

	log.Debug("handler_get_user",
		"target_user_id", userID,
	)

	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		log.Warn("handler_get_user_not_found",
			"target_user_id", userID,
		)
		response.Fail(c, http.StatusNotFound, shared.ErrCodeUserNotFound, "user not found")
		return
	}

	log.Debug("handler_get_user_success",
		"target_user_id", userID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, profile)
}
