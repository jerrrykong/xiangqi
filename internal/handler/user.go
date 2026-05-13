package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/middleware"
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
	userID := middleware.GetUserID(c)

	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, profile)
}

// UpdateProfile updates the current user's profile
// PATCH /users/me
func (h *UserHandler) UpdateProfile(c *gin.Context) {
	userID := middleware.GetUserID(c)

	var req service.UpdateProfileRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	if err := h.userSvc.UpdateProfile(c.Request.Context(), userID, &req); err != nil {
		response.InternalError(c)
		return
	}

	// Return updated profile
	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, profile)
}

// GetRankings returns the rankings
// GET /users/rankings
func (h *UserHandler) GetRankings(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	resp, err := h.userSvc.GetRankings(c.Request.Context(), &service.RankingsRequest{
		Page:     page,
		PageSize: pageSize,
	})
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// GetHistory returns a user's game history
// GET /users/:id/history
func (h *UserHandler) GetHistory(c *gin.Context) {
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		response.BadRequest(c, "invalid user ID")
		return
	}

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	gameType := c.DefaultQuery("type", "")

	resp, err := h.userSvc.GetHistory(c.Request.Context(), userID, &service.HistoryRequest{
		Page:     page,
		PageSize: pageSize,
		Type:     gameType,
	})
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// GetUser returns a specific user's profile
// GET /users/:id
func (h *UserHandler) GetUser(c *gin.Context) {
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		response.BadRequest(c, "invalid user ID")
		return
	}

	profile, err := h.userSvc.GetUser(c.Request.Context(), userID)
	if err != nil {
		response.Fail(c, http.StatusNotFound, shared.ErrCodeUserNotFound, "user not found")
		return
	}

	response.OK(c, profile)
}
