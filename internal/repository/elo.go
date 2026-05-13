package repository

import (
	"context"
	"database/sql"

	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
)

// EloRepository handles ELO rating data access
type EloRepository struct {
	db *gorm.DB
}

// NewEloRepository creates a new EloRepository
func NewEloRepository(db *gorm.DB) *EloRepository {
	return &EloRepository{db: db}
}

// Create creates a new ELO rating record
func (r *EloRepository) Create(ctx context.Context, elo *model.EloRating) error {
	return r.db.WithContext(ctx).Create(elo).Error
}

// GetByUserID retrieves ELO rating by user ID
func (r *EloRepository) GetByUserID(ctx context.Context, userID int64) (*model.EloRating, error) {
	var elo model.EloRating
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).First(&elo).Error
	if err != nil {
		return nil, err
	}
	return &elo, nil
}

// Update updates an ELO rating
func (r *EloRepository) Update(ctx context.Context, elo *model.EloRating) error {
	return r.db.WithContext(ctx).Save(elo).Error
}

// UpdateRating updates a user's rating
func (r *EloRepository) UpdateRating(ctx context.Context, userID int64, rating, gamesCount int) error {
	return r.db.WithContext(ctx).Model(&model.EloRating{}).
		Where("user_id = ?", userID).
		Updates(map[string]interface{}{
			"rating":      rating,
			"games_count": gamesCount,
		}).Error
}

// IncrementGamesCount increments the games count for a user
func (r *EloRepository) IncrementGamesCount(ctx context.Context, userID int64) error {
	return r.db.WithContext(ctx).Model(&model.EloRating{}).
		Where("user_id = ?", userID).
		UpdateColumn("games_count", gorm.Expr("games_count + ?", 1)).Error
}

// GetRankings gets user rankings sorted by rating
func (r *EloRepository) GetRankings(ctx context.Context, page, pageSize int) ([]model.RankingItem, int64, error) {
	var items []model.RankingItem
	var total int64

	// Count total
	if err := r.db.WithContext(ctx).Model(&model.EloRating{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// Get paginated rankings
	offset := (page - 1) * pageSize
	rows, err := r.db.WithContext(ctx).
		Table("elo_ratings").
		Select("elo_ratings.user_id, elo_ratings.rating, elo_ratings.games_count, users.username, users.nickname").
		Joins("LEFT JOIN users ON users.id = elo_ratings.user_id").
		Order("elo_ratings.rating DESC").
		Offset(offset).
		Limit(pageSize).
		Rows()

	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	rank := offset + 1
	for rows.Next() {
		var item model.RankingItem
		var nickname sql.NullString
		if err := rows.Scan(&item.UserID, &item.Rating, &item.GamesCount, &item.Username, &nickname); err != nil {
			return nil, 0, err
		}
		if nickname.Valid {
			item.Nickname = nickname.String
		}
		item.Rank = rank
		items = append(items, item)
		rank++
	}

	return items, total, nil
}

// CreateHistory creates an ELO history record
func (r *EloRepository) CreateHistory(ctx context.Context, history *model.EloHistory) error {
	return r.db.WithContext(ctx).Create(history).Error
}

// GetHistory gets ELO history for a user
func (r *EloRepository) GetHistory(ctx context.Context, userID int64, page, pageSize int) ([]model.EloHistory, int64, error) {
	var histories []model.EloHistory
	var total int64

	query := r.db.WithContext(ctx).Model(&model.EloHistory{}).Where("user_id = ?", userID)

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	if err := query.Order("created_at DESC").Offset(offset).Limit(pageSize).Find(&histories).Error; err != nil {
		return nil, 0, err
	}

	return histories, total, nil
}

// GetOrCreate gets or creates an ELO rating for a user
func (r *EloRepository) GetOrCreate(ctx context.Context, userID int64) (*model.EloRating, error) {
	elo, err := r.GetByUserID(ctx, userID)
	if err == gorm.ErrRecordNotFound {
		elo = &model.EloRating{
			UserID:     userID,
			Rating:     model.DefaultEloRating,
			GamesCount: 0,
		}
		if err := r.Create(ctx, elo); err != nil {
			return nil, err
		}
		return elo, nil
	}
	return elo, err
}
