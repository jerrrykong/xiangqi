package handler

import (
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/middleware"
	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/pkg/log"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
	"github.com/jerrykong/xiangqi/internal/service"
	"github.com/jerrykong/xiangqi/shared"
)

// RoomHandler handles room-related endpoints
type RoomHandler struct {
	roomSvc *service.RoomService
}

// NewRoomHandler creates a new RoomHandler
func NewRoomHandler(roomSvc *service.RoomService) *RoomHandler {
	return &RoomHandler{roomSvc: roomSvc}
}

// CreateRoom creates a new PvP room
// POST /rooms
func (h *RoomHandler) CreateRoom(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)
	username := middleware.GetUsername(c)

	log.Info("handler_create_room_start",
		"user_id", userID,
		"username", username,
	)

	resp, err := h.roomSvc.CreateRoom(c.Request.Context(), userID)
	if err != nil {
		log.Error("handler_create_room_error",
			"user_id", userID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrAlreadyInRoom) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in a room")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_create_room_success",
		"user_id", userID,
		"room_id", resp.RoomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// ListRooms returns waiting rooms
// GET /rooms
func (h *RoomHandler) ListRooms(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	log.Debug("handler_list_rooms",
		"user_id", userID,
		"page", page,
		"page_size", pageSize,
	)

	rooms, total, err := h.roomSvc.ListRooms(c.Request.Context(), page, pageSize)
	if err != nil {
		log.Error("handler_list_rooms_error",
			"user_id", userID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		response.InternalError(c)
		return
	}

	log.Debug("handler_list_rooms_success",
		"user_id", userID,
		"total", total,
		"count", len(rooms),
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{
		"total": total,
		"rooms": rooms,
	})
}

// GetMyRoom returns the room the current user is in
// GET /rooms/me
func (h *RoomHandler) GetMyRoom(c *gin.Context) {
	start := time.Now()
	userID := middleware.GetUserID(c)

	log.Debug("handler_get_my_room",
		"user_id", userID,
	)

	room, err := h.roomSvc.GetUserCurrentRoom(c.Request.Context(), userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Debug("handler_get_my_room_not_in_room",
				"user_id", userID,
			)
			response.Fail(c, http.StatusNotFound, shared.ErrCodeNotInRoom, "not in any room")
			return
		}
		log.Error("handler_get_my_room_error",
			"user_id", userID,
			"error", err.Error(),
		)
		response.InternalError(c)
		return
	}
	if room == nil {
		log.Debug("handler_get_my_room_not_in_room",
			"user_id", userID,
		)
		response.Fail(c, http.StatusNotFound, shared.ErrCodeNotInRoom, "not in any room")
		return
	}

	log.Debug("handler_get_my_room_success",
		"user_id", userID,
		"room_id", room.ID,
		"status", room.Status,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	// Build response
	resp := gin.H{
		"room_id": room.ID,
		"status":  room.Status,
		"type":    room.Type,
	}

	// If game is in progress, get session info from Redis and determine yourSide
	if room.Status == model.RoomStatusPlaying {
		sessionInfo, err := h.roomSvc.GetGameSession(c.Request.Context(), room.ID)
		if err != nil {
			log.Warn("handler_get_my_room_session_error",
				"user_id", userID,
				"room_id", room.ID,
				"error", err.Error(),
			)
		}
		if sessionInfo != nil {
			resp["game_ws_url"] = sessionInfo.WsURL
			resp["game_token"] = sessionInfo.SessionToken
		}

		// Determine which side the user is on
		if room.RedUserID.Valid && room.RedUserID.Int64 == userID {
			resp["your_side"] = "red"
		} else if room.BlackUserID.Valid && room.BlackUserID.Int64 == userID {
			resp["your_side"] = "black"
		}
	}

	response.OK(c, resp)
}

// GetRoom returns a room's details
// GET /rooms/:id
func (h *RoomHandler) GetRoom(c *gin.Context) {
	start := time.Now()
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	log.Debug("handler_get_room",
		"user_id", userID,
		"room_id", roomID,
	)

	detail, err := h.roomSvc.GetRoomDetail(c.Request.Context(), roomID, userID)
	if err != nil {
		log.Warn("handler_get_room_error",
			"user_id", userID,
			"room_id", roomID,
			"error", err.Error(),
		)
		response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
		return
	}

	log.Debug("handler_get_room_success",
		"user_id", userID,
		"room_id", roomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, detail)
}

// JoinRoom joins a room
// POST /rooms/:id/join
func (h *RoomHandler) JoinRoom(c *gin.Context) {
	start := time.Now()
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)
	username := middleware.GetUsername(c)

	log.Info("handler_join_room_start",
		"user_id", userID,
		"username", username,
		"room_id", roomID,
	)

	resp, err := h.roomSvc.JoinRoom(c.Request.Context(), roomID, userID)
	if err != nil {
		log.Warn("handler_join_room_error",
			"user_id", userID,
			"room_id", roomID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		switch {
		case errors.Is(err, service.ErrRoomNotFound):
			response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
		case errors.Is(err, service.ErrRoomFull):
			response.Fail(c, http.StatusConflict, shared.ErrCodeRoomFull, "room is full")
		case errors.Is(err, service.ErrRoomNotWaiting):
			response.Fail(c, http.StatusConflict, shared.ErrCodeRoomNotWaiting, "room is not waiting")
		case errors.Is(err, service.ErrAlreadyInRoom):
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in a room")
		case errors.Is(err, service.ErrCannotJoinOwnRoom):
			response.Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, "cannot join your own room")
		default:
			response.InternalError(c)
		}
		return
	}

	log.Info("handler_join_room_success",
		"user_id", userID,
		"room_id", roomID,
		"your_side", resp.YourSide,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// PlayerReady marks the player as ready
// POST /rooms/:id/ready
func (h *RoomHandler) PlayerReady(c *gin.Context) {
	start := time.Now()
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	log.Info("handler_player_ready_start",
		"user_id", userID,
		"room_id", roomID,
	)

	resp, err := h.roomSvc.PlayerReady(c.Request.Context(), roomID, userID)
	if err != nil {
		log.Error("handler_player_ready_error",
			"user_id", userID,
			"room_id", roomID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrRoomNotFound) {
			response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_player_ready_success",
		"user_id", userID,
		"room_id", roomID,
		"red_ready", resp.RedReady,
		"black_ready", resp.BlackReady,
		"game_started", resp.GameStarted,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, resp)
}

// LeaveRoom makes the player leave the room
// POST /rooms/:id/leave
func (h *RoomHandler) LeaveRoom(c *gin.Context) {
	start := time.Now()
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	log.Info("handler_leave_room_start",
		"user_id", userID,
		"room_id", roomID,
	)

	if err := h.roomSvc.LeaveRoom(c.Request.Context(), roomID, userID); err != nil {
		log.Warn("handler_leave_room_error",
			"user_id", userID,
			"room_id", roomID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		if errors.Is(err, service.ErrRoomNotFound) {
			response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
			return
		}
		if errors.Is(err, service.ErrRoomNotWaiting) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeRoomNotWaiting, "cannot leave during game")
			return
		}
		response.InternalError(c)
		return
	}

	log.Info("handler_leave_room_success",
		"user_id", userID,
		"room_id", roomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "left"})
}

// DeleteRoom deletes a room (owner only)
// DELETE /rooms/:id
func (h *RoomHandler) DeleteRoom(c *gin.Context) {
	start := time.Now()
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	log.Info("handler_delete_room_start",
		"user_id", userID,
		"room_id", roomID,
	)

	if err := h.roomSvc.DeleteRoom(c.Request.Context(), roomID, userID); err != nil {
		log.Warn("handler_delete_room_error",
			"user_id", userID,
			"room_id", roomID,
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		switch {
		case errors.Is(err, service.ErrRoomNotFound):
			response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
		case errors.Is(err, service.ErrNotRoomOwner):
			response.Fail(c, http.StatusForbidden, shared.ErrCodeNotRoomOwner, "not room owner")
		case errors.Is(err, service.ErrRoomNotWaiting):
			response.Fail(c, http.StatusConflict, shared.ErrCodeRoomNotWaiting, "cannot delete room during game")
		default:
			response.InternalError(c)
		}
		return
	}

	log.Info("handler_delete_room_success",
		"user_id", userID,
		"room_id", roomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	response.OK(c, gin.H{"status": "deleted"})
}
