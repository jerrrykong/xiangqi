package service

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/repository"
)

// RoomService errors
var (
	ErrRoomNotFound     = errors.New("room not found")
	ErrRoomFull         = errors.New("room is full")
	ErrRoomNotWaiting   = errors.New("room is not waiting")
	ErrAlreadyInRoom    = errors.New("already in a room")
	ErrNotRoomOwner     = errors.New("not room owner")
	ErrCannotJoinOwnRoom = errors.New("cannot join your own room")
)

// RoomService handles room-related business logic
type RoomService struct {
	roomRepo   *repository.RoomRepository
	userRepo   *repository.UserRepository
	eloRepo    *repository.EloRepository
	gameProxy  *GameProxy
	redis      *redis.Client
}

// NewRoomService creates a new RoomService
func NewRoomService(
	roomRepo *repository.RoomRepository,
	userRepo *repository.UserRepository,
	eloRepo *repository.EloRepository,
	gameProxy *GameProxy,
	redisClient *redis.Client,
) *RoomService {
	return &RoomService{
		roomRepo:  roomRepo,
		userRepo:  userRepo,
		eloRepo:   eloRepo,
		gameProxy: gameProxy,
		redis:     redisClient,
	}
}

// CreateRoom creates a new PvP room
func (s *RoomService) CreateRoom(ctx context.Context, userID int64) (*model.CreateRoomResponse, error) {
	// Check if user is already in a room
	inRoom, err := s.roomRepo.IsUserInRoom(ctx, userID)
	if err != nil {
		return nil, err
	}
	if inRoom {
		return nil, ErrAlreadyInRoom
	}

	// Create room
	room := &model.Room{
		ID:        uuid.New().String(),
		Type:      model.RoomTypePvP,
		Status:    model.RoomStatusWaiting,
		CreatedBy: userID,
	}

	// Set creator as red player
	room.RedUserID.Int64 = userID
	room.RedUserID.Valid = true
	room.RedReady = true // Creator is auto-ready

	if err := s.roomRepo.Create(ctx, room); err != nil {
		return nil, err
	}

	return &model.CreateRoomResponse{
		RoomID:    room.ID,
		RoomType:  room.Type,
		Status:    room.Status,
		CreatedAt: room.CreatedAt.Format(time.RFC3339),
	}, nil
}

// ListRooms lists waiting rooms
func (s *RoomService) ListRooms(ctx context.Context, page, pageSize int) ([]model.RoomListItem, int64, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 20
	}
	return s.roomRepo.GetWaitingRooms(ctx, page, pageSize)
}

// JoinRoom allows a user to join a room
func (s *RoomService) JoinRoom(ctx context.Context, roomID string, userID int64) (*model.JoinRoomResponse, error) {
	// Check if user is already in a room
	inRoom, err := s.roomRepo.IsUserInRoom(ctx, userID)
	if err != nil {
		return nil, err
	}
	if inRoom {
		return nil, ErrAlreadyInRoom
	}

	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrRoomNotFound
		}
		return nil, err
	}

	// Check if room is waiting
	if room.Status != model.RoomStatusWaiting {
		return nil, ErrRoomNotWaiting
	}

	// Check if room has red player
	if !room.RedUserID.Valid {
		return nil, ErrRoomNotWaiting
	}

	// Cannot join own room
	if room.RedUserID.Int64 == userID {
		return nil, ErrCannotJoinOwnRoom
	}

	// Join as black
	if err := s.roomRepo.JoinRoom(ctx, roomID, userID, false); err != nil {
		return nil, err
	}

	// Get opponent info
	opponentUser, err := s.userRepo.GetByID(ctx, room.RedUserID.Int64)
	if err != nil {
		return nil, err
	}

	opponentElo, _ := s.eloRepo.GetByUserID(ctx, room.RedUserID.Int64)

	return &model.JoinRoomResponse{
		RoomID:   roomID,
		YourSide: "black",
		Opponent: &model.OpponentInfo{
			UserID:   opponentUser.ID,
			Username: opponentUser.Username,
			Rating:   opponentElo.Rating,
		},
		Status: model.RoomStatusReady,
	}, nil
}

// PlayerReady marks a player as ready
func (s *RoomService) PlayerReady(ctx context.Context, roomID string, userID int64) (*model.ReadyResponse, error) {
	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrRoomNotFound
		}
		return nil, err
	}

	// Determine if user is red or black
	var isRed bool
	if room.RedUserID.Valid && room.RedUserID.Int64 == userID {
		isRed = true
	} else if room.BlackUserID.Valid && room.BlackUserID.Int64 == userID {
		isRed = false
	} else {
		return nil, ErrRoomNotFound
	}

	// Set ready status
	if err := s.roomRepo.SetPlayerReady(ctx, roomID, isRed, true); err != nil {
		return nil, err
	}

	// Reload room
	room, err = s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		return nil, err
	}

	resp := &model.ReadyResponse{
		RoomID:     roomID,
		RedReady:   room.RedReady,
		BlackReady: room.BlackReady,
	}

	// Check if both players are ready
	if room.RedReady && room.BlackReady {
		// Update room status to playing
		if err := s.roomRepo.StartGame(ctx, roomID); err != nil {
			return nil, err
		}

		// Get opponent info for game proxy
		var redID, blackID int64
		var redUsername, blackUsername string

		if room.RedUserID.Valid {
			redID = room.RedUserID.Int64
			redUser, _ := s.userRepo.GetByID(ctx, redID)
			if redUser != nil {
				redUsername = redUser.Username
			}
		}
		if room.BlackUserID.Valid {
			blackID = room.BlackUserID.Int64
			blackUser, _ := s.userRepo.GetByID(ctx, blackID)
			if blackUser != nil {
				blackUsername = blackUser.Username
			}
		}

		// Call game proxy to assign game
		assignResp, err := s.gameProxy.AssignGame(ctx, &AssignRequest{
			RoomID:   roomID,
			GameType: "pvp",
			Players: []PlayerInfo{
				{UserID: redID, Username: redUsername, Side: "red"},
				{UserID: blackID, Username: blackUsername, Side: "black"},
			},
		})

		if err == nil && assignResp != nil {
			// Update room with game ID
			_ = s.roomRepo.SetGameID(ctx, roomID, assignResp.GameID)

			resp.GameStarted = true
			resp.GameWsURL = assignResp.WsURL
			resp.GameToken = assignResp.SessionToken
		}
	}

	return resp, nil
}

// LeaveRoom allows a player to leave a room
func (s *RoomService) LeaveRoom(ctx context.Context, roomID string, userID int64) error {
	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return ErrRoomNotFound
		}
		return err
	}

	// Check if user is in this room
	isInRoom := (room.RedUserID.Valid && room.RedUserID.Int64 == userID) ||
		(room.BlackUserID.Valid && room.BlackUserID.Int64 == userID)

	if !isInRoom {
		return ErrRoomNotFound
	}

	// Can only leave waiting or ready rooms
	if room.Status == model.RoomStatusPlaying {
		return ErrRoomNotWaiting
	}

	return s.roomRepo.LeaveRoom(ctx, roomID, userID)
}

// DeleteRoom deletes a room (only owner, only waiting rooms)
func (s *RoomService) DeleteRoom(ctx context.Context, roomID string, userID int64) error {
	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return ErrRoomNotFound
		}
		return err
	}

	// Check if user is owner
	if room.CreatedBy != userID {
		return ErrNotRoomOwner
	}

	// Can only delete waiting rooms
	if room.Status != model.RoomStatusWaiting {
		return ErrRoomNotWaiting
	}

	return s.roomRepo.Delete(ctx, roomID)
}

// GetUserCurrentRoom gets the room a user is currently in
func (s *RoomService) GetUserCurrentRoom(ctx context.Context, userID int64) (*model.Room, error) {
	return s.roomRepo.GetUserCurrentRoom(ctx, userID)
}

// CreatePvERoom creates a room for PvE game
func (s *RoomService) CreatePvERoom(ctx context.Context, userID int64, difficulty int) (*model.ReadyResponse, error) {
	// Create room
	room := &model.Room{
		ID:        uuid.New().String(),
		Type:      model.RoomTypePvE,
		Status:    model.RoomStatusWaiting,
		CreatedBy: userID,
	}
	room.RedUserID.Int64 = userID
	room.RedUserID.Valid = true

	if difficulty > 0 {
		room.Difficulty.Int32 = int32(difficulty)
		room.Difficulty.Valid = true
	}

	if err := s.roomRepo.Create(ctx, room); err != nil {
		return nil, err
	}

	// Get user info
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Call game proxy for PvE
	assignResp, err := s.gameProxy.AssignGame(ctx, &AssignRequest{
		RoomID:     room.ID,
		GameType:   "pve",
		Players:    []PlayerInfo{{UserID: userID, Username: user.Username, Side: "red"}},
		Difficulty: &difficulty,
	})

	if err != nil {
		return nil, err
	}

	// Update room status
	_ = s.roomRepo.SetGameID(ctx, room.ID, assignResp.GameID)
	_ = s.roomRepo.StartGame(ctx, room.ID)

	return &model.ReadyResponse{
		RoomID:      room.ID,
		RedReady:    true,
		BlackReady:  false,
		GameStarted:  true,
		GameWsURL:   assignResp.WsURL,
		GameToken:   assignResp.SessionToken,
	}, nil
}

// CacheRoomState caches room state in Redis
func (s *RoomService) CacheRoomState(ctx context.Context, room *model.Room) error {
	if s.redis == nil {
		return nil
	}

	data, err := json.Marshal(room)
	if err != nil {
		return err
	}

	key := "room:" + room.ID + ":state"
	return s.redis.Set(ctx, key, data, 24*time.Hour).Err()
}

// GetCachedRoomState gets cached room state from Redis
func (s *RoomService) GetCachedRoomState(ctx context.Context, roomID string) (*model.Room, error) {
	if s.redis == nil {
		return nil, nil
	}

	key := "room:" + roomID + ":state"
	data, err := s.redis.Get(ctx, key).Bytes()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return nil, nil
		}
		return nil, err
	}

	var room model.Room
	if err := json.Unmarshal(data, &room); err != nil {
		return nil, err
	}

	return &room, nil
}

// DeleteCachedRoomState deletes cached room state from Redis
func (s *RoomService) DeleteCachedRoomState(ctx context.Context, roomID string) error {
	if s.redis == nil {
		return nil
	}

	key := "room:" + roomID + ":state"
	return s.redis.Del(ctx, key).Err()
}
