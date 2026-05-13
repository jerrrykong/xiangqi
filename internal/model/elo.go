package model

import (
	"time"
)

// EloRating represents a user's ELO rating
type EloRating struct {
	UserID     int64     `json:"user_id" gorm:"primaryKey"`
	Rating     int       `json:"rating" gorm:"default:1500"`
	GamesCount int       `json:"games_count" gorm:"default:0"`
	UpdatedAt  time.Time `json:"updated_at" gorm:"autoUpdateTime"`
	User       *User     `json:"user,omitempty" gorm:"foreignKey:UserID"`
}

// TableName returns the table name for EloRating
func (EloRating) TableName() string {
	return "elo_ratings"
}

// EloHistory represents a record of ELO rating changes
type EloHistory struct {
	ID        int64     `json:"id" gorm:"primaryKey;autoIncrement"`
	UserID    int64     `json:"user_id" gorm:"type:bigint;not null;index"`
	Rating    int       `json:"rating" gorm:"not null"`
	Change    int       `json:"change" gorm:"not null"`     // Rating change for this game (+10/-15)
	GameID    int64     `json:"game_id,omitempty" gorm:"type:bigint"`
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime"`
}

// TableName returns the table name for EloHistory
func (EloHistory) TableName() string {
	return "elo_history"
}

// DefaultEloRating is the starting ELO rating for new users
const DefaultEloRating = 1500
