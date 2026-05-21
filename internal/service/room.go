package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/pkg/log"
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

// Timeout constants
const (
	WaitingRoomTimeout = 30 * time.Minute // 等待中的房间 30 分钟超时
	PlayingRoomTimeout = 2 * time.Hour    // 对局中的房间 2 小时超时
	CheckInterval     = 1 * time.Minute   // 检查间隔
)

// RoomTimeout 房间超时信息（内存缓存）
type RoomTimeout struct {
	RoomID    string
	CreatedAt time.Time
	PlayingAt time.Time             // 进入对局的时间，零值表示未开始
	Status    model.RoomStatus      // 房间状态
}

// TimeoutChecker 超时检查器
type TimeoutChecker struct {
	rooms    map[string]*RoomTimeout // roomID -> timeout info
	mu       sync.RWMutex
	roomRepo *repository.RoomRepository
	stopCh   chan struct{}
	running  bool
}

// NewTimeoutChecker 创建超时检查器
func NewTimeoutChecker(roomRepo *repository.RoomRepository) *TimeoutChecker {
	return &TimeoutChecker{
		rooms:    make(map[string]*RoomTimeout),
		roomRepo: roomRepo,
		stopCh:   make(chan struct{}),
	}
}

// LoadFromDB 从数据库加载所有非结束状态的房间
func (tc *TimeoutChecker) LoadFromDB(ctx context.Context) error {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	log.Info("timeout_checker_load_from_db", "step", "start")

	rooms, err := tc.roomRepo.GetActiveRooms(ctx)
	if err != nil {
		log.Error("timeout_checker_load_from_db_error",
			"error", err.Error(),
		)
		return err
	}

	for _, room := range rooms {
		rt := &RoomTimeout{
			RoomID:    room.ID,
			CreatedAt: room.CreatedAt,
			Status:    room.Status,
		}

		// 如果是对局中状态，设置 PlayingAt
		if room.Status == model.RoomStatusPlaying {
			// 使用当前时间作为开始时间
			rt.PlayingAt = time.Now()
		}

		tc.rooms[room.ID] = rt
	}

	log.Info("timeout_checker_load_from_db_success",
		"total_rooms", len(rooms),
	)

	return nil
}

// AddRoom 添加房间到缓存
func (tc *TimeoutChecker) AddRoom(roomID string, createdAt time.Time) {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	tc.rooms[roomID] = &RoomTimeout{
		RoomID:    roomID,
		CreatedAt: createdAt,
		Status:    model.RoomStatusWaiting,
	}

	log.Debug("timeout_checker_add_room",
		"room_id", roomID,
	)
}

// RemoveRoom 从缓存移除房间
func (tc *TimeoutChecker) RemoveRoom(roomID string) {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	delete(tc.rooms, roomID)

	log.Debug("timeout_checker_remove_room",
		"room_id", roomID,
	)
}

// StartGame 更新房间状态为对局中
func (tc *TimeoutChecker) StartGame(roomID string) {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	if rt, ok := tc.rooms[roomID]; ok {
		rt.Status = model.RoomStatusPlaying
		rt.PlayingAt = time.Now()

		log.Debug("timeout_checker_game_started",
			"room_id", roomID,
		)
	}
}

// Start 启动超时检查（定时任务）
func (tc *TimeoutChecker) Start(ctx context.Context) {
	tc.mu.Lock()
	if tc.running {
		tc.mu.Unlock()
		return
	}
	tc.running = true
	tc.mu.Unlock()

	log.Info("timeout_checker_started")

	ticker := time.NewTicker(CheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			tc.checkAndCleanup(ctx)
		case <-tc.stopCh:
			log.Info("timeout_checker_stopped")
			return
		case <-ctx.Done():
			log.Info("timeout_checker_context_done")
			return
		}
	}
}

// Stop 停止超时检查
func (tc *TimeoutChecker) Stop() {
	tc.mu.Lock()
	defer tc.mu.Unlock()

	if tc.running {
		close(tc.stopCh)
		tc.running = false
		tc.stopCh = make(chan struct{})
	}
}

// checkAndCleanup 检查并清理超时房间
func (tc *TimeoutChecker) checkAndCleanup(ctx context.Context) {
	tc.mu.Lock()
	// 复制一份 keys 避免在遍历时修改
	roomIDs := make([]string, 0, len(tc.rooms))
	for id := range tc.rooms {
		roomIDs = append(roomIDs, id)
	}
	tc.mu.Unlock()

	now := time.Now()
	cleaned := 0

	for _, roomID := range roomIDs {
		tc.mu.RLock()
		rt, ok := tc.rooms[roomID]
		tc.mu.RUnlock()

		if !ok {
			continue
		}

		var expired bool
		var reason string

		if rt.Status == model.RoomStatusWaiting {
			// 等待中的房间：30 分钟超时
			if now.Sub(rt.CreatedAt) > WaitingRoomTimeout {
				expired = true
				reason = "waiting_timeout"
			}
		} else if rt.Status == model.RoomStatusPlaying {
			// 对局中的房间：2 小时超时
			if !rt.PlayingAt.IsZero() && now.Sub(rt.PlayingAt) > PlayingRoomTimeout {
				expired = true
				reason = "playing_timeout"
			}
		}

		if expired {
			log.Info("timeout_checker_room_expired",
				"room_id", roomID,
				"reason", reason,
			)

			// 删除房间（忽略错误）
			_ = tc.roomRepo.Delete(ctx, roomID)

			// 从缓存移除
			tc.RemoveRoom(roomID)

			cleaned++
		}
	}

	if cleaned > 0 {
		log.Info("timeout_checker_cleanup_summary",
			"cleaned_rooms", cleaned,
		)
	}
}

// RoomService handles room-related business logic
type RoomService struct {
	roomRepo       *repository.RoomRepository
	userRepo       *repository.UserRepository
	eloRepo        *repository.EloRepository
	gameProxy      *GameProxy
	redis          *redis.Client
	timeoutChecker *TimeoutChecker
}

// NewRoomService creates a new RoomService
func NewRoomService(
	roomRepo *repository.RoomRepository,
	userRepo *repository.UserRepository,
	eloRepo *repository.EloRepository,
	gameProxy *GameProxy,
	redisClient *redis.Client,
) *RoomService {
	tc := NewTimeoutChecker(roomRepo)
	return &RoomService{
		roomRepo:       roomRepo,
		userRepo:       userRepo,
		eloRepo:        eloRepo,
		gameProxy:      gameProxy,
		redis:          redisClient,
		timeoutChecker: tc,
	}
}

// StartTimeoutChecker 启动超时检查器
func (s *RoomService) StartTimeoutChecker(ctx context.Context) error {
	if err := s.timeoutChecker.LoadFromDB(ctx); err != nil {
		return err
	}
	go s.timeoutChecker.Start(ctx)
	return nil
}

// StopTimeoutChecker 停止超时检查器
func (s *RoomService) StopTimeoutChecker() {
	s.timeoutChecker.Stop()
}

// CreateRoom creates a new PvP room
func (s *RoomService) CreateRoom(ctx context.Context, userID int64) (*model.CreateRoomResponse, error) {
	start := time.Now()

	log.Info("room_service_create_room",
		"user_id", userID,
	)

	// Check if user is already in a room
	inRoom, err := s.roomRepo.IsUserInRoom(ctx, userID)
	if err != nil {
		log.Error("room_service_create_room_error",
			"user_id", userID,
			"step", "check_user_in_room",
			"error", err.Error(),
		)
		return nil, err
	}
	if inRoom {
		log.Warn("room_service_create_room_rejected",
			"user_id", userID,
			"reason", "already_in_room",
		)
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
	// Note: Creator is NOT auto-ready, they need to click Ready like everyone else

	if err := s.roomRepo.Create(ctx, room); err != nil {
		log.Error("room_service_create_room_error",
			"user_id", userID,
			"step", "create_room",
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		return nil, err
	}

	// 添加到超时检查缓存
	s.timeoutChecker.AddRoom(room.ID, room.CreatedAt)

	log.Info("room_service_create_room_success",
		"user_id", userID,
		"room_id", room.ID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

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

	log.Debug("room_service_list_rooms",
		"page", page,
		"page_size", pageSize,
	)

	rooms, total, err := s.roomRepo.GetWaitingRooms(ctx, page, pageSize)
	if err != nil {
		log.Error("room_service_list_rooms_error",
			"error", err.Error(),
		)
		return nil, 0, err
	}

	log.Debug("room_service_list_rooms_success",
		"total", total,
		"returned", len(rooms),
	)

	return rooms, total, nil
}

// JoinRoom allows a user to join a room
func (s *RoomService) JoinRoom(ctx context.Context, roomID string, userID int64) (*model.JoinRoomResponse, error) {
	start := time.Now()

	log.Info("room_service_join_room",
		"user_id", userID,
		"room_id", roomID,
	)

	// Check if user is already in a room
	inRoom, err := s.roomRepo.IsUserInRoom(ctx, userID)
	if err != nil {
		log.Error("room_service_join_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "check_user_in_room",
			"error", err.Error(),
		)
		return nil, err
	}
	if inRoom {
		log.Warn("room_service_join_room_rejected",
			"user_id", userID,
			"room_id", roomID,
			"reason", "already_in_room",
		)
		return nil, ErrAlreadyInRoom
	}

	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Warn("room_service_join_room_rejected",
				"user_id", userID,
				"room_id", roomID,
				"reason", "room_not_found",
			)
			return nil, ErrRoomNotFound
		}
		log.Error("room_service_join_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return nil, err
	}

	// Check if room is waiting
	if room.Status != model.RoomStatusWaiting {
		log.Warn("room_service_join_room_rejected",
			"user_id", userID,
			"room_id", roomID,
			"reason", "room_not_waiting",
			"current_status", room.Status,
		)
		return nil, ErrRoomNotWaiting
	}

	// Check if room has red player
	if !room.RedUserID.Valid {
		log.Warn("room_service_join_room_rejected",
			"user_id", userID,
			"room_id", roomID,
			"reason", "no_red_player",
		)
		return nil, ErrRoomNotWaiting
	}

	// Cannot join own room
	if room.RedUserID.Int64 == userID {
		log.Warn("room_service_join_room_rejected",
			"user_id", userID,
			"room_id", roomID,
			"reason", "cannot_join_own_room",
		)
		return nil, ErrCannotJoinOwnRoom
	}

	// Join as black
	if err := s.roomRepo.JoinRoom(ctx, roomID, userID, false); err != nil {
		log.Error("room_service_join_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "join_room",
			"error", err.Error(),
		)
		return nil, err
	}

	// Get opponent info
	opponentUser, err := s.userRepo.GetByID(ctx, room.RedUserID.Int64)
	if err != nil {
		log.Error("room_service_join_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_opponent",
			"error", err.Error(),
		)
		return nil, err
	}

	opponentElo, _ := s.eloRepo.GetByUserID(ctx, room.RedUserID.Int64)

	log.Info("room_service_join_room_success",
		"user_id", userID,
		"room_id", roomID,
		"opponent_id", opponentUser.ID,
		"opponent_name", opponentUser.Username,
		"duration_ms", time.Since(start).Milliseconds(),
	)

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
	start := time.Now()

	log.Info("room_service_player_ready",
		"user_id", userID,
		"room_id", roomID,
	)

	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Warn("room_service_player_ready_error",
				"user_id", userID,
				"room_id", roomID,
				"reason", "room_not_found",
			)
			return nil, ErrRoomNotFound
		}
		log.Error("room_service_player_ready_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return nil, err
	}

	// Determine if user is red or black
	var isRed bool
	var side string
	if room.RedUserID.Valid && room.RedUserID.Int64 == userID {
		isRed = true
		side = "red"
	} else if room.BlackUserID.Valid && room.BlackUserID.Int64 == userID {
		isRed = false
		side = "black"
	} else {
		log.Warn("room_service_player_ready_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "user_not_in_room",
		)
		return nil, ErrRoomNotFound
	}

	log.Debug("room_service_player_ready_set",
		"user_id", userID,
		"room_id", roomID,
		"side", side,
		"is_red", isRed,
	)

	// Set ready status
	if err := s.roomRepo.SetPlayerReady(ctx, roomID, isRed, true); err != nil {
		log.Error("room_service_player_ready_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "set_ready",
			"error", err.Error(),
		)
		return nil, err
	}

	// Reload room
	room, err = s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		log.Error("room_service_player_ready_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "reload_room",
			"error", err.Error(),
		)
		return nil, err
	}

	resp := &model.ReadyResponse{
		RoomID:     roomID,
		RedReady:   room.RedReady,
		BlackReady: room.BlackReady,
	}

	// Check if both players are ready
	if room.RedReady && room.BlackReady {
		log.Info("room_service_both_ready",
			"room_id", roomID,
			"red_ready", room.RedReady,
			"black_ready", room.BlackReady,
		)

		// Update room status to playing
		if err := s.roomRepo.StartGame(ctx, roomID); err != nil {
			log.Error("room_service_both_ready_error",
				"room_id", roomID,
				"step", "start_game",
				"error", err.Error(),
			)
			return nil, err
		}

		// 更新超时检查器状态为 playing
		s.timeoutChecker.StartGame(roomID)

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

		log.Info("room_service_assigning_game",
			"room_id", roomID,
			"red_id", redID,
			"red_username", redUsername,
			"black_id", blackID,
			"black_username", blackUsername,
		)

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
			log.Info("room_service_game_assigned",
				"room_id", roomID,
				"game_id", assignResp.GameID,
				"ws_url", assignResp.WsURL,
			)

			// Update room with game ID
			_ = s.roomRepo.SetGameID(ctx, roomID, assignResp.GameID)

			resp.GameStarted = true
			resp.GameWsURL = assignResp.WsURL

			// Give each player their own token
			if assignResp.PlayerTokens != nil {
				key := fmt.Sprintf("%d", userID)
				if tok, ok := assignResp.PlayerTokens[key]; ok {
					resp.GameToken = tok
				} else {
					resp.GameToken = assignResp.SessionToken
				}
			} else {
				resp.GameToken = assignResp.SessionToken
			}
		} else if err != nil {
			log.Error("room_service_game_assign_error",
				"room_id", roomID,
				"error", err.Error(),
			)
		}
	}

	log.Info("room_service_player_ready_success",
		"user_id", userID,
		"room_id", roomID,
		"side", side,
		"red_ready", resp.RedReady,
		"black_ready", resp.BlackReady,
		"game_started", resp.GameStarted,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	return resp, nil
}

// LeaveRoom allows a player to leave a room
func (s *RoomService) LeaveRoom(ctx context.Context, roomID string, userID int64) error {
	start := time.Now()

	log.Info("room_service_leave_room",
		"user_id", userID,
		"room_id", roomID,
	)

	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Warn("room_service_leave_room_error",
				"user_id", userID,
				"room_id", roomID,
				"reason", "room_not_found",
			)
			return ErrRoomNotFound
		}
		log.Error("room_service_leave_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return err
	}

	// Check if user is in this room
	isInRoom := (room.RedUserID.Valid && room.RedUserID.Int64 == userID) ||
		(room.BlackUserID.Valid && room.BlackUserID.Int64 == userID)

	if !isInRoom {
		log.Warn("room_service_leave_room_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "user_not_in_room",
		)
		return ErrRoomNotFound
	}

	// Can only leave waiting or ready rooms
	if room.Status == model.RoomStatusPlaying {
		log.Warn("room_service_leave_room_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "cannot_leave_during_game",
			"status", room.Status,
		)
		return ErrRoomNotWaiting
	}

	if err := s.roomRepo.LeaveRoom(ctx, roomID, userID); err != nil {
		log.Error("room_service_leave_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "leave_room",
			"error", err.Error(),
		)
		return err
	}

	// 从超时检查缓存移除
	s.timeoutChecker.RemoveRoom(roomID)

	log.Info("room_service_leave_room_success",
		"user_id", userID,
		"room_id", roomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	return nil
}

// DeleteRoom deletes a room (only owner, only waiting rooms)
func (s *RoomService) DeleteRoom(ctx context.Context, roomID string, userID int64) error {
	start := time.Now()

	log.Info("room_service_delete_room",
		"user_id", userID,
		"room_id", roomID,
	)

	// Get room
	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Warn("room_service_delete_room_error",
				"user_id", userID,
				"room_id", roomID,
				"reason", "room_not_found",
			)
			return ErrRoomNotFound
		}
		log.Error("room_service_delete_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return err
	}

	// Check if user is owner
	if room.CreatedBy != userID {
		log.Warn("room_service_delete_room_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "not_room_owner",
			"owner_id", room.CreatedBy,
		)
		return ErrNotRoomOwner
	}

	// Can only delete waiting rooms
	if room.Status != model.RoomStatusWaiting {
		log.Warn("room_service_delete_room_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "cannot_delete_during_game",
			"status", room.Status,
		)
		return ErrRoomNotWaiting
	}

	if err := s.roomRepo.Delete(ctx, roomID); err != nil {
		log.Error("room_service_delete_room_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "delete_room",
			"error", err.Error(),
		)
		return err
	}

	// 从超时检查缓存移除
	s.timeoutChecker.RemoveRoom(roomID)

	log.Info("room_service_delete_room_success",
		"user_id", userID,
		"room_id", roomID,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	return nil
}

// GetUserCurrentRoom gets the room a user is currently in
func (s *RoomService) GetUserCurrentRoom(ctx context.Context, userID int64) (*model.Room, error) {
	log.Debug("room_service_get_user_current_room",
		"user_id", userID,
	)

	room, err := s.roomRepo.GetUserCurrentRoom(ctx, userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Debug("room_service_get_user_current_room_not_found",
				"user_id", userID,
			)
			return nil, err
		}
		log.Error("room_service_get_user_current_room_error",
			"user_id", userID,
			"error", err.Error(),
		)
		return nil, err
	}

	log.Debug("room_service_get_user_current_room_success",
		"user_id", userID,
		"room_id", room.ID,
		"status", room.Status,
	)

	return room, nil
}

// GetGameSession retrieves game session info for a room
func (s *RoomService) GetGameSession(ctx context.Context, roomID string) (*SessionInfo, error) {
	if s.gameProxy == nil {
		return nil, errors.New("game proxy not available")
	}
	return s.gameProxy.GetSession(ctx, roomID)
}

// GetGameSessionForUser retrieves game session info with per-player token resolved
func (s *RoomService) GetGameSessionForUser(ctx context.Context, roomID string, userID int64) (*SessionInfo, error) {
	if s.gameProxy == nil {
		return nil, errors.New("game proxy not available")
	}
	return s.gameProxy.GetSessionForUser(ctx, roomID, userID)
}

// ResetRoomStatus resets a room's status to waiting (used when game session is lost)
func (s *RoomService) ResetRoomStatus(ctx context.Context, roomID string) error {
	log.Debug("room_service_reset_room_status",
		"room_id", roomID,
	)

	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		log.Error("room_service_reset_room_status_error",
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return err
	}

	room.Status = model.RoomStatusWaiting
	room.RedReady = false
	room.BlackReady = false

	if err := s.roomRepo.Update(ctx, room); err != nil {
		log.Error("room_service_reset_room_status_error",
			"room_id", roomID,
			"step", "update_room",
			"error", err.Error(),
		)
		return err
	}

	log.Info("room_service_reset_room_status_success",
		"room_id", roomID,
	)

	return nil
}

// GetRoomDetail returns full room details including player information
// Returns 404 if the room doesn't exist OR the user is not in the room
func (s *RoomService) GetRoomDetail(ctx context.Context, roomID string, userID int64) (*model.RoomDetailResponse, error) {
	log.Debug("room_service_get_room_detail",
		"user_id", userID,
		"room_id", roomID,
	)

	room, err := s.roomRepo.GetByID(ctx, roomID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			log.Warn("room_service_get_room_detail_error",
				"user_id", userID,
				"room_id", roomID,
				"reason", "room_not_found",
			)
			return nil, ErrRoomNotFound
		}
		log.Error("room_service_get_room_detail_error",
			"user_id", userID,
			"room_id", roomID,
			"step", "get_room",
			"error", err.Error(),
		)
		return nil, err
	}

	// Only allow participants to view room details
	isParticipant := (room.RedUserID.Valid && room.RedUserID.Int64 == userID) ||
		(room.BlackUserID.Valid && room.BlackUserID.Int64 == userID)
	if !isParticipant {
		log.Warn("room_service_get_room_detail_error",
			"user_id", userID,
			"room_id", roomID,
			"reason", "not_participant",
		)
		return nil, ErrRoomNotFound
	}

	detail := &model.RoomDetailResponse{
		RoomID:     room.ID,
		Status:     room.Status,
		Type:       room.Type,
		RedReady:   room.RedReady,
		BlackReady: room.BlackReady,
	}

	// Determine user's side
	if room.RedUserID.Valid && room.RedUserID.Int64 == userID {
		detail.YourSide = "red"
	} else if room.BlackUserID.Valid && room.BlackUserID.Int64 == userID {
		detail.YourSide = "black"
	}

	if room.RedUserID.Valid {
		u, _ := s.userRepo.GetByID(ctx, room.RedUserID.Int64)
		elo, _ := s.eloRepo.GetByUserID(ctx, room.RedUserID.Int64)
		if u != nil {
			detail.RedUser = &model.RoomUserInfo{
				UserID:   u.ID,
				Username: u.Username,
			}
			if elo != nil {
				detail.RedUser.Rating = elo.Rating
			}
		}
	}

	if room.BlackUserID.Valid {
		u, _ := s.userRepo.GetByID(ctx, room.BlackUserID.Int64)
		elo, _ := s.eloRepo.GetByUserID(ctx, room.BlackUserID.Int64)
		if u != nil {
			detail.BlackUser = &model.RoomUserInfo{
				UserID:   u.ID,
				Username: u.Username,
			}
			if elo != nil {
				detail.BlackUser.Rating = elo.Rating
			}
		}
	}

	// If game is in progress, get session info from Redis
	if room.Status == model.RoomStatusPlaying {
		sessionInfo, err := s.GetGameSessionForUser(ctx, roomID, userID)
		if err != nil {
			log.Warn("room_service_get_room_detail_session_error",
				"room_id", roomID,
				"error", err.Error(),
			)
		}
		if sessionInfo != nil {
			detail.GameWsURL = sessionInfo.WsURL
			detail.GameToken = sessionInfo.SessionToken
		} else {
			// Redis 数据丢失，重置房间状态
			log.Warn("room_service_get_room_detail_session_missing",
				"room_id", roomID,
				"action", "reset_status_to_waiting",
			)
			room.Status = model.RoomStatusWaiting
			room.RedReady = false
			room.BlackReady = false
			if updateErr := s.roomRepo.Update(ctx, room); updateErr != nil {
				log.Error("room_service_get_room_detail_reset_error",
					"room_id", roomID,
					"error", updateErr.Error(),
				)
			}

			// 更新返回的状态
			detail.Status = model.RoomStatusWaiting
			detail.RedReady = false
			detail.BlackReady = false
		}
	}

	log.Debug("room_service_get_room_detail_success",
		"user_id", userID,
		"room_id", roomID,
		"status", room.Status,
		"red_ready", room.RedReady,
		"black_ready", room.BlackReady,
	)

	return detail, nil
}

// CreatePvERoom creates a room for PvE game
func (s *RoomService) CreatePvERoom(ctx context.Context, userID int64, difficulty int) (*model.ReadyResponse, error) {
	start := time.Now()

	log.Info("room_service_create_pve_room",
		"user_id", userID,
		"difficulty", difficulty,
	)

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
		log.Error("room_service_create_pve_room_error",
			"user_id", userID,
			"step", "create_room",
			"error", err.Error(),
		)
		return nil, err
	}

	// Get user info
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		log.Error("room_service_create_pve_room_error",
			"user_id", userID,
			"step", "get_user",
			"error", err.Error(),
		)
		return nil, err
	}

	log.Info("room_service_pve_assigning_game",
		"user_id", userID,
		"room_id", room.ID,
		"username", user.Username,
		"difficulty", difficulty,
	)

	// Call game proxy for PvE
	assignResp, err := s.gameProxy.AssignGame(ctx, &AssignRequest{
		RoomID:     room.ID,
		GameType:   "pve",
		Players:    []PlayerInfo{{UserID: userID, Username: user.Username, Side: "red"}},
		Difficulty: &difficulty,
	})

	if err != nil {
		log.Error("room_service_create_pve_room_error",
			"user_id", userID,
			"step", "assign_game",
			"error", err.Error(),
		)
		return nil, err
	}

	// Update room status
	_ = s.roomRepo.SetGameID(ctx, room.ID, assignResp.GameID)
	_ = s.roomRepo.StartGame(ctx, room.ID)

	log.Info("room_service_create_pve_room_success",
		"user_id", userID,
		"room_id", room.ID,
		"game_id", assignResp.GameID,
		"ws_url", assignResp.WsURL,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	return &model.ReadyResponse{
		RoomID:      room.ID,
		RedReady:    true,
		BlackReady:  false,
		GameStarted: true,
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
		log.Error("room_service_cache_state_error",
			"room_id", room.ID,
			"error", err.Error(),
		)
		return err
	}

	key := "room:" + room.ID + ":state"
	if err := s.redis.Set(ctx, key, data, 24*time.Hour).Err(); err != nil {
		log.Error("room_service_cache_state_error",
			"room_id", room.ID,
			"step", "redis_set",
			"error", err.Error(),
		)
		return err
	}

	log.Debug("room_service_cache_state",
		"room_id", room.ID,
	)

	return nil
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
			log.Debug("room_service_cache_miss",
				"room_id", roomID,
			)
			return nil, nil
		}
		log.Error("room_service_cache_get_error",
			"room_id", roomID,
			"error", err.Error(),
		)
		return nil, err
	}

	var room model.Room
	if err := json.Unmarshal(data, &room); err != nil {
		log.Error("room_service_cache_unmarshal_error",
			"room_id", roomID,
			"error", err.Error(),
		)
		return nil, err
	}

	log.Debug("room_service_cache_hit",
		"room_id", roomID,
	)

	return &room, nil
}

// DeleteCachedRoomState deletes cached room state from Redis
func (s *RoomService) DeleteCachedRoomState(ctx context.Context, roomID string) error {
	if s.redis == nil {
		return nil
	}

	key := "room:" + roomID + ":state"
	if err := s.redis.Del(ctx, key).Err(); err != nil {
		log.Error("room_service_cache_delete_error",
			"room_id", roomID,
			"error", err.Error(),
		)
		return err
	}

	log.Debug("room_service_cache_delete",
		"room_id", roomID,
	)

	return nil
}
