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
	userID := middleware.GetUserID(c)

	resp, err := h.roomSvc.CreateRoom(c.Request.Context(), userID)
	if err != nil {
		if errors.Is(err, service.ErrAlreadyInRoom) {
			response.Fail(c, http.StatusConflict, shared.ErrCodeAlreadyInRoom, "already in a room")
			return
		}
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// ListRooms returns waiting rooms
// GET /rooms
func (h *RoomHandler) ListRooms(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))

	rooms, total, err := h.roomSvc.ListRooms(c.Request.Context(), page, pageSize)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, gin.H{
		"total": total,
		"rooms": rooms,
	})
}

// GetMyRoom returns the room the current user is in
// GET /rooms/me
func (h *RoomHandler) GetMyRoom(c *gin.Context) {
	userID := middleware.GetUserID(c)

	room, err := h.roomSvc.GetUserCurrentRoom(c.Request.Context(), userID)
	if err != nil {
		response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "not in any room")
		return
	}
	if room == nil {
		response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "not in any room")
		return
	}

	response.OK(c, gin.H{
		"room_id": room.ID,
		"status":  room.Status,
		"type":    room.Type,
	})
}

// GetRoom returns a room's details
// GET /rooms/:id
func (h *RoomHandler) GetRoom(c *gin.Context) {
	roomID := c.Param("id")

	room, err := h.roomSvc.GetUserCurrentRoom(c.Request.Context(), middleware.GetUserID(c))
	if err != nil {
		response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
		return
	}

	if room.ID != roomID {
		response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
		return
	}

	response.OK(c, room)
}

// JoinRoom joins a room
// POST /rooms/:id/join
func (h *RoomHandler) JoinRoom(c *gin.Context) {
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	resp, err := h.roomSvc.JoinRoom(c.Request.Context(), roomID, userID)
	if err != nil {
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

	response.OK(c, resp)
}

// PlayerReady marks the player as ready
// POST /rooms/:id/ready
func (h *RoomHandler) PlayerReady(c *gin.Context) {
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	resp, err := h.roomSvc.PlayerReady(c.Request.Context(), roomID, userID)
	if err != nil {
		if errors.Is(err, service.ErrRoomNotFound) {
			response.Fail(c, http.StatusNotFound, shared.ErrCodeRoomNotFound, "room not found")
			return
		}
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}

// LeaveRoom makes the player leave the room
// POST /rooms/:id/leave
func (h *RoomHandler) LeaveRoom(c *gin.Context) {
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	if err := h.roomSvc.LeaveRoom(c.Request.Context(), roomID, userID); err != nil {
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

	response.OK(c, gin.H{"status": "left"})
}

// DeleteRoom deletes a room (owner only)
// DELETE /rooms/:id
func (h *RoomHandler) DeleteRoom(c *gin.Context) {
	roomID := c.Param("id")
	userID := middleware.GetUserID(c)

	if err := h.roomSvc.DeleteRoom(c.Request.Context(), roomID, userID); err != nil {
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

	response.OK(c, gin.H{"status": "deleted"})
}
