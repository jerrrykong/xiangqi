package repository

import (
	"context"

	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
)

// GameRepository handles game history data access
type GameRepository struct {
	db *gorm.DB
}

// NewGameRepository creates a new GameRepository
func NewGameRepository(db *gorm.DB) *GameRepository {
	return &GameRepository{db: db}
}

// Create creates a new game history record
func (r *GameRepository) Create(ctx context.Context, game *model.GameHistory) error {
	return r.db.WithContext(ctx).Create(game).Error
}

// GetByID retrieves a game history by ID
func (r *GameRepository) GetByID(ctx context.Context, id int64) (*model.GameHistory, error) {
	var game model.GameHistory
	err := r.db.WithContext(ctx).First(&game, id).Error
	if err != nil {
		return nil, err
	}
	return &game, nil
}

// GetByRoomID retrieves game history by room ID
func (r *GameRepository) GetByRoomID(ctx context.Context, roomID string) (*model.GameHistory, error) {
	var game model.GameHistory
	err := r.db.WithContext(ctx).Where("room_id = ?", roomID).First(&game).Error
	if err != nil {
		return nil, err
	}
	return &game, nil
}

// GetUserHistory gets game history for a user
func (r *GameRepository) GetUserHistory(ctx context.Context, userID int64, page, pageSize int, gameType string) ([]model.GameHistory, int64, error) {
	var games []model.GameHistory
	var total int64

	query := r.db.WithContext(ctx).Model(&model.GameHistory{}).
		Where("red_user_id = ? OR black_user_id = ?", userID, userID)

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	if err := query.Order("end_time DESC").Offset(offset).Limit(pageSize).Find(&games).Error; err != nil {
		return nil, 0, err
	}

	return games, total, nil
}

// GetTotalGamesCount returns the total number of completed games
func (r *GameRepository) GetTotalGamesCount(ctx context.Context) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&model.GameHistory{}).Count(&count).Error
	return count, err
}

// GetTodayGamesCount returns the number of games played today
func (r *GameRepository) GetTodayGamesCount(ctx context.Context) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&model.GameHistory{}).
		Where("DATE(end_time) = CURRENT_DATE").
		Count(&count).Error
	return count, err
}
