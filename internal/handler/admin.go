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
	start := time.Now()
	adminID := middleware.GetUserID(c)
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	search := c.Query("search")

	var banned *bool
	if bannedStr := c.Query("banned"); bannedStr != "" {
		b := bannedStr == "true"
		banned = &b
	}

	log.Debug("handler_admin_list_users",
		"admin_id", adminID,
		"page", page,
		"page_size", pageSize,
		"search", search,
	)

	resp, err := h.adminSvc.ListUsers(c.Request.Context(), &service.ListUsersOptions{
		Page:     page,
		PageSize: pageSize,
		Search:   search,
		Banned:   banned,
	})
	if err != nil {
		log.Error("handler_admin_list_users_error",
			"admin_id", adminID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_admin_list_users_success",
		"admin_id", adminID,
		"total", resp.Total,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// BanUser bans or unbans a user
// PATCH /admin/users/:id/ban
func (h *AdminHandler) BanUser(c *gin.Context) {
	start := time.Now()
	adminID := middleware.GetUserID(c)
	targetUserIDStr := c.Param("id")
	targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64)
	if err != nil {
		log.Warn("handler_admin_ban_user_bad_request",
			"admin_id", adminID,
			"target_user_id_str", targetUserIDStr,
		)
		response.BadRequest(c, "invalid user ID")
		return
	}

	var req service.BanUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Warn("handler_admin_ban_user_bad_body",
			"admin_id", adminID,
			"target_user_id", targetUserID,
		)
		response.BadRequest(c, "invalid request body")
		return
	}

	log.Info("handler_admin_ban_user_start",
		"admin_id", adminID,
		"target_user_id", targetUserID,
		"banned", req.Banned,
	)

	if err := h.adminSvc.BanUser(c.Request.Context(), targetUserID, &req); err != nil {
		log.Error("handler_admin_ban_user_error",
			"admin_id", adminID,
			"target_user_id", targetUserID,
			"error", err.Error(),
		)
		response.BadRequest(c, err.Error())
		return
	}

	log.Info("handler_admin_ban_user_success",
		"admin_id", adminID,
		"target_user_id", targetUserID,
		"banned", req.Banned,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "updated"})
}

// GetStats returns admin statistics
// GET /admin/stats
func (h *AdminHandler) GetStats(c *gin.Context) {
	start := time.Now()
	adminID := middleware.GetUserID(c)

	log.Debug("handler_admin_get_stats",
		"admin_id", adminID,
	)

	stats, err := h.adminSvc.GetStats(c.Request.Context())
	if err != nil {
		log.Error("handler_admin_get_stats_error",
			"admin_id", adminID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_admin_get_stats_success",
		"admin_id", adminID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, stats)
}

// ListModels returns a list of AI models
// GET /admin/models
func (h *AdminHandler) ListModels(c *gin.Context) {
	start := time.Now()
	adminID := middleware.GetUserID(c)

	log.Debug("handler_admin_list_models",
		"admin_id", adminID,
	)

	models, err := h.adminSvc.ListModels(c.Request.Context())
	if err != nil {
		log.Error("handler_admin_list_models_error",
			"admin_id", adminID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_admin_list_models_success",
		"admin_id", adminID,
		"count", len(models),
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"models": models})
}

// PublishModel publishes an AI model
// PATCH /admin/models/:id/publish
func (h *AdminHandler) PublishModel(c *gin.Context) {
	start := time.Now()
	adminID := middleware.GetUserID(c)
	modelIDStr := c.Param("id")
	modelID, err := strconv.ParseInt(modelIDStr, 10, 64)
	if err != nil {
		log.Warn("handler_admin_publish_model_bad_request",
			"admin_id", adminID,
			"model_id_str", modelIDStr,
		)
		response.BadRequest(c, "invalid model ID")
		return
	}

	log.Info("handler_admin_publish_model_start",
		"admin_id", adminID,
		"model_id", modelID,
	)

	if err := h.adminSvc.PublishModel(c.Request.Context(), modelID); err != nil {
		log.Error("handler_admin_publish_model_error",
			"admin_id", adminID,
			"model_id", modelID,
			"error", err.Error(),
		)
		response.BadRequest(c, err.Error())
		return
	}

	log.Info("handler_admin_publish_model_success",
		"admin_id", adminID,
		"model_id", modelID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "published"})
}

// UploadModel handles model upload (placeholder)
// POST /admin/models/upload
func (h *AdminHandler) UploadModel(c *gin.Context) {
	start := time.Now()
	adminID := middleware.GetUserID(c)

	log.Debug("handler_admin_upload_model",
		"admin_id", adminID,
	)

	// This would handle multipart file upload
	// For now, return a placeholder response
	log.Debug("handler_admin_upload_model_completed",
		"admin_id", adminID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

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
	start := time.Now()

	var req service.GameResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Error("handler_game_result_bad_request",
			"error", err.Error(),
		)
		response.BadRequest(c, "invalid request body")
		return
	}

	log.Info("handler_game_result_start",
		"room_id", req.RoomID,
		"result", req.Result,
		"winner", req.Winner,
	)

	// Process game result
	if err := h.eloSvc.ProcessGameResult(c.Request.Context(), &req); err != nil {
		log.Error("handler_game_result_process_error",
			"room_id", req.RoomID,
			"error", err.Error(),
		)
		// Log error but return success to prevent retry loops
		c.JSON(http.StatusOK, gin.H{"status": "error", "message": err.Error()})
		return
	}

	log.Info("handler_game_result_success",
		"room_id", req.RoomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "ok"})
}
