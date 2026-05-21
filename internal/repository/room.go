package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
)

// RoomRepository handles room data access
type RoomRepository struct {
	db *gorm.DB
}

// NewRoomRepository creates a new RoomRepository
func NewRoomRepository(db *gorm.DB) *RoomRepository {
	return &RoomRepository{db: db}
}

// Create creates a new room
func (r *RoomRepository) Create(ctx context.Context, room *model.Room) error {
	if room.ID == "" {
		room.ID = uuid.New().String()
	}
	return r.db.WithContext(ctx).Create(room).Error
}

// GetByID retrieves a room by ID
func (r *RoomRepository) GetByID(ctx context.Context, id string) (*model.Room, error) {
	var room model.Room
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&room).Error
	if err != nil {
		return nil, err
	}
	return &room, nil
}

// GetByIDWithUsers retrieves a room with user information
func (r *RoomRepository) GetByIDWithUsers(ctx context.Context, id string) (*model.Room, error) {
	var room model.Room
	err := r.db.WithContext(ctx).
		Preload("RedUser").
		Preload("BlackUser").
		Where("id = ?", id).First(&room).Error
	if err != nil {
		return nil, err
	}
	return &room, nil
}

// Update updates a room
func (r *RoomRepository) Update(ctx context.Context, room *model.Room) error {
	return r.db.WithContext(ctx).Save(room).Error
}

// UpdateStatus updates the room status
func (r *RoomRepository) UpdateStatus(ctx context.Context, roomID string, status model.RoomStatus) error {
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Update("status", status).Error
}

// SetPlayerReady marks a player as ready
func (r *RoomRepository) SetPlayerReady(ctx context.Context, roomID string, isRed bool, ready bool) error {
	if isRed {
		return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Update("red_ready", ready).Error
	}
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Update("black_ready", ready).Error
}

// JoinRoom adds a player to a room
func (r *RoomRepository) JoinRoom(ctx context.Context, roomID string, userID int64, isRed bool) error {
	if isRed {
		return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Updates(map[string]interface{}{
			"red_user_id": userID,
			"status":      model.RoomStatusReady,
		}).Error
	}
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Updates(map[string]interface{}{
		"black_user_id": userID,
		"status":        model.RoomStatusReady,
	}).Error
}

// SetGameID sets the game ID for a room
func (r *RoomRepository) SetGameID(ctx context.Context, roomID, gameID string) error {
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Update("game_id", gameID).Error
}

// StartGame marks a room as playing
func (r *RoomRepository) StartGame(ctx context.Context, roomID string) error {
	now := time.Now()
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Updates(map[string]interface{}{
		"status":     model.RoomStatusPlaying,
		"started_at": now,
	}).Error
}

// FinishGame marks a room as finished
func (r *RoomRepository) FinishGame(ctx context.Context, roomID, winner string) error {
	now := time.Now()
	return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Updates(map[string]interface{}{
		"status":     model.RoomStatusFinished,
		"winner":     winner,
		"ended_at":   now,
	}).Error
}

// GetUserCurrentRoom gets the room a user is currently in
func (r *RoomRepository) GetUserCurrentRoom(ctx context.Context, userID int64) (*model.Room, error) {
	var room model.Room
	err := r.db.WithContext(ctx).
		Where("red_user_id = ? OR black_user_id = ?", userID, userID).
		Where("status IN ?", []model.RoomStatus{model.RoomStatusWaiting, model.RoomStatusReady, model.RoomStatusPlaying}).
		First(&room).Error
	if err != nil {
		return nil, err
	}
	return &room, nil
}

// GetWaitingRooms gets rooms waiting for players
func (r *RoomRepository) GetWaitingRooms(ctx context.Context, page, pageSize int) ([]model.RoomListItem, int64, error) {
	var rooms []model.Room
	var total int64

	// 只返回有红方的房间（red_user_id IS NOT NULL）
	query := r.db.WithContext(ctx).Model(&model.Room{}).
		Where("status = ?", model.RoomStatusWaiting).
		Where("red_user_id IS NOT NULL")

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	if err := query.Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&rooms).Error; err != nil {
		return nil, 0, err
	}

	// Get usernames for created_by users
	var items []model.RoomListItem
	for _, room := range rooms {
		var username string
		r.db.WithContext(ctx).Model(&model.User{}).Where("id = ?", room.CreatedBy).Select("username").Scan(&username)
		items = append(items, model.RoomListItem{
			RoomID:    room.ID,
			CreatedBy: room.CreatedBy,
			Username:  username,
			CreatedAt: room.CreatedAt.Format(time.RFC3339),
		})
	}

	return items, total, nil
}

// Delete deletes a room
func (r *RoomRepository) Delete(ctx context.Context, roomID string) error {
	return r.db.WithContext(ctx).Where("id = ?", roomID).Delete(&model.Room{}).Error
}

// LeaveRoom removes a player from a room
// If the red player leaves, the room is deleted (a room without a red player is invalid)
// If the black player leaves, only the black player info is cleared
func (r *RoomRepository) LeaveRoom(ctx context.Context, roomID string, userID int64) error {
	room, err := r.GetByID(ctx, roomID)
	if err != nil {
		return err
	}

	// If red player leaves, delete the room (no red player = invalid room)
	if room.RedUserID.Valid && room.RedUserID.Int64 == userID {
		return r.db.WithContext(ctx).Where("id = ?", roomID).Delete(&model.Room{}).Error
	}

	// If black player leaves, just clear black player info
	if room.BlackUserID.Valid && room.BlackUserID.Int64 == userID {
		return r.db.WithContext(ctx).Model(&model.Room{}).Where("id = ?", roomID).Updates(map[string]interface{}{
			"black_user_id": nil,
			"black_ready":   false,
			"status":        model.RoomStatusWaiting,
		}).Error
	}

	return nil
}

// IsUserInRoom checks if a user is in any active room
func (r *RoomRepository) IsUserInRoom(ctx context.Context, userID int64) (bool, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&model.Room{}).
		Where("(red_user_id = ? OR black_user_id = ?) AND status IN ?", userID, userID,
			[]model.RoomStatus{model.RoomStatusWaiting, model.RoomStatusReady, model.RoomStatusPlaying}).
		Count(&count).Error
	return count > 0, err
}

// GetActiveRooms gets all rooms that are not finished (waiting, ready, playing)
func (r *RoomRepository) GetActiveRooms(ctx context.Context) ([]*model.Room, error) {
	var rooms []*model.Room
	err := r.db.WithContext(ctx).
		Where("status IN ?", []model.RoomStatus{model.RoomStatusWaiting, model.RoomStatusReady, model.RoomStatusPlaying}).
		Find(&rooms).Error
	return rooms, err
}
