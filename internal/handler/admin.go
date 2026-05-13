package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/pkg/response"
	"github.com/jerrykong/xiangqi/internal/service"
)

// AdminHandler handles admin-related endpoints
type AdminHandler struct {
	adminSvc *service.AdminService
}

// NewAdminHandler creates a new AdminHandler
func NewAdminHandler(adminSvc *service.AdminService) *AdminHandler {
	return &AdminHandler{adminSvc: adminSvc}
}

// ListUsers returns a list of users
// GET /admin/users
func (h *AdminHandler) ListUsers(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	search := c.Query("search")

	var banned *bool
	if bannedStr := c.Query("banned"); bannedStr != "" {
		b := bannedStr == "true"
		banned = &b
	}

	resp, err := h.adminSvc.ListUsers(c.Request.Context(), &service.ListUsersOptions{
		Page:     page,
		PageSize: pageSize,
		Search:   search,
		Banned:   banned,
	})
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// BanUser bans or unbans a user
// PATCH /admin/users/:id/ban
func (h *AdminHandler) BanUser(c *gin.Context) {
	userIDStr := c.Param("id")
	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		response.BadRequest(c, "invalid user ID")
		return
	}

	var req service.BanUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	if err := h.adminSvc.BanUser(c.Request.Context(), userID, &req); err != nil {
		response.BadRequest(c, err.Error())
		return
	}

	response.OK(c, gin.H{"status": "updated"})
}

// GetStats returns admin statistics
// GET /admin/stats
func (h *AdminHandler) GetStats(c *gin.Context) {
	stats, err := h.adminSvc.GetStats(c.Request.Context())
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, stats)
}

// ListModels returns a list of AI models
// GET /admin/models
func (h *AdminHandler) ListModels(c *gin.Context) {
	models, err := h.adminSvc.ListModels(c.Request.Context())
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, gin.H{"models": models})
}

// PublishModel publishes an AI model
// PATCH /admin/models/:id/publish
func (h *AdminHandler) PublishModel(c *gin.Context) {
	modelIDStr := c.Param("id")
	modelID, err := strconv.ParseInt(modelIDStr, 10, 64)
	if err != nil {
		response.BadRequest(c, "invalid model ID")
		return
	}

	if err := h.adminSvc.PublishModel(c.Request.Context(), modelID); err != nil {
		response.BadRequest(c, err.Error())
		return
	}

	response.OK(c, gin.H{"status": "published"})
}

// UploadModel handles model upload (placeholder)
// POST /admin/models/upload
func (h *AdminHandler) UploadModel(c *gin.Context) {
	// This would handle multipart file upload
	// For now, return a placeholder response
	response.OK(c, gin.H{
		"status": "upload_not_implemented",
	})
}

// InternalHandler handles internal callbacks from Game service
type InternalHandler struct {
	roomSvc *service.RoomService
	eloSvc  *service.EloService
}

// NewInternalHandler creates a new InternalHandler
func NewInternalHandler(
	roomSvc *service.RoomService,
	eloSvc *service.EloService,
) *InternalHandler {
	return &InternalHandler{
		roomSvc: roomSvc,
		eloSvc:  eloSvc,
	}
}

// HandleGameResult handles game result callback
// POST /internal/game/result
func (h *InternalHandler) HandleGameResult(c *gin.Context) {
	var req service.GameResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	// Process game result
	if err := h.eloSvc.ProcessGameResult(c.Request.Context(), &req); err != nil {
		// Log error but return success to prevent retry loops
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": err.Error()})
		return
	}

	response.OK(c, gin.H{"status": "ok"})
}
