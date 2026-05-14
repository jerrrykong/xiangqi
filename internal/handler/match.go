package handler

import (
	"errors"
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

// MatchHandler handles match-related endpoints
type MatchHandler struct {
	matchSvc *service.MatchService
	roomSvc  *service.RoomService
}

// NewMatchHandler creates a new MatchHandler
func NewMatchHandler(matchSvc *service.MatchService, roomSvc *service.RoomService) *MatchHandler {
	return &MatchHandler{
		matchSvc: matchSvc,
		roomSvc:  roomSvc,
	}
}

// JoinPvP joins the PvP match queue
// POST /match/pvp
func (h *MatchHandler) JoinPvP(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)
	username := middleware.GetUsername(c)

	log.Info("handler_join_pvp_start",
		"user_id", userID,
		"username", username,
	)

	resp, err := h.matchSvc.JoinQueue(c.Request.Context(), userID)
	if err != nil {
		log.Warn("handler_join_pvp_error",
			"user_id", userID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrAlreadyInQueue) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in match queue")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_join_pvp_success",
		"user_id", userID,
		"queue_id", resp.QueueID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// LeavePvP leaves the PvP match queue
// DELETE /match/pvp
func (h *MatchHandler) LeavePvP(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)

	log.Info("handler_leave_pvp_start",
		"user_id", userID,
	)

	if err := h.matchSvc.LeaveQueue(c.Request.Context(), userID); err != nil {
		log.Warn("handler_leave_pvp_error",
			"user_id", userID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrNotInQueue) {
			response.Fail(c, http.StatusBadRequest, shared.ErrCodeNotInRoom, "not in match queue")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_leave_pvp_success",
		"user_id", userID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "left_queue"})
}

// GetStatus returns the current match status
// GET /match/status
func (h *MatchHandler) GetStatus(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)

	log.Debug("handler_get_match_status",
		"user_id", userID,
	)

	status, err := h.matchSvc.GetQueueStatus(c.Request.Context(), userID)
	if err != nil {
		log.Error("handler_get_match_status_error",
			"user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_get_match_status_success",
		"user_id", userID,
		"status", status.Status,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, status)
}

// JoinPvE joins a PvE game
// POST /match/pve/:level
func (h *MatchHandler) JoinPvE(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)
	username := middleware.GetUsername(c)

	levelStr := c.Param("level")
	level, err := strconv.Atoi(levelStr)
	if err != nil || level < 1 || level > 5 {
		log.Warn("handler_join_pve_bad_request",
			"user_id", userID,
			"level_str", levelStr,
		)
		response.Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, "invalid difficulty level (1-5)")
		return
	}

	log.Info("handler_join_pve_start",
		"user_id", userID,
		"username", username,
		"level", level,
	)

	resp, err := h.roomSvc.CreatePvERoom(c.Request.Context(), userID, level)
	if err != nil {
		log.Error("handler_join_pve_error",
			"user_id", userID,
			"level", level,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrAlreadyInRoom) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in a game")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_join_pve_success",
		"user_id", userID,
		"room_id", resp.RoomID,
		"level", level,
		"game_started", resp.GameStarted,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{
		"room_id":    resp.RoomID,
		"difficulty": level,
		"game_ws_url": resp.GameWsURL,
		"game_token":  resp.GameToken,
		"your_side":  "red",
	})
}
