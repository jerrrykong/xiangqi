package handler

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/middleware"
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
	userID := middleware.GetUserID(c)

	resp, err := h.matchSvc.JoinQueue(c.Request.Context(), userID)
	if err != nil {
		if errors.Is(err, service.ErrAlreadyInQueue) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in match queue")
			return
		}
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// LeavePvP leaves the PvP match queue
// DELETE /match/pvp
func (h *MatchHandler) LeavePvP(c *gin.Context) {
	userID := middleware.GetUserID(c)

	if err := h.matchSvc.LeaveQueue(c.Request.Context(), userID); err != nil {
		if errors.Is(err, service.ErrNotInQueue) {
			response.Fail(c, http.StatusBadRequest, shared.ErrCodeNotInRoom, "not in match queue")
			return
		}
		response.InternalError(c)
		return
	}

	response.OK(c, gin.H{"status": "left_queue"})
}

// GetStatus returns the current match status
// GET /match/status
func (h *MatchHandler) GetStatus(c *gin.Context) {
	userID := middleware.GetUserID(c)

	status, err := h.matchSvc.GetQueueStatus(c.Request.Context(), userID)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, status)
}

// JoinPvE joins a PvE game
// POST /match/pve/:level
func (h *MatchHandler) JoinPvE(c *gin.Context) {
	userID := middleware.GetUserID(c)

	levelStr := c.Param("level")
	level, err := strconv.Atoi(levelStr)
	if err != nil || level < 1 || level > 5 {
		response.Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, "invalid difficulty level (1-5)")
		return
	}

	resp, err := h.roomSvc.CreatePvERoom(c.Request.Context(), userID, level)
	if err != nil {
		if errors.Is(err, service.ErrAlreadyInRoom) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in a game")
			return
		}
		response.InternalError(c)
		return
	}

	response.OK(c, gin.H{
		"room_id":    resp.RoomID,
		"difficulty": level,
		"game_ws_url": resp.GameWsURL,
		"game_token":  resp.GameToken,
		"your_side":  "red",
	})
}
