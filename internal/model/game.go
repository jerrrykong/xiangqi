package model

import (
	"time"
)

// GameHistory represents a completed game record
type GameHistory struct {
	ID          int64     `json:"id" gorm:"primaryKey;autoIncrement"`
	RoomID      string    `json:"room_id" gorm:"type:uuid;not null;index"`
	Winner      string    `json:"winner" gorm:"type:varchar(8);not null"` // red/black/draw
	Result      int       `json:"result" gorm:"type:int;not null"`       // GameResult enum
	TotalMoves  int       `json:"total_moves" gorm:"not null"`
	StartTime   time.Time `json:"start_time" gorm:"not null"`
	EndTime     time.Time `json:"end_time" gorm:"not null"`
	PvELevel    *int      `json:"pve_level,omitempty" gorm:"type:int"`    // PvE difficulty
	RedUserID   int64     `json:"red_user_id" gorm:"type:bigint"`
	BlackUserID int64     `json:"black_user_id" gorm:"type:bigint"`
}

// TableName returns the table name for GameHistory
func (GameHistory) TableName() string {
	return "game_history"
}

// GameResult constants
const (
	GameResultOngoing         = 0  // Game in progress
	GameResultRedWins         = 1  // Red wins
	GameResultBlackWins       = 2  // Black wins
	GameResultDraw            = 3  // Draw
	GameResultRedResign       = 4  // Red resigns
	GameResultBlackResign     = 5  // Black resigns
	GameResultRedTimeout      = 6  // Red times out
	GameResultBlackTimeout    = 7  // Black times out
	GameResultRedDisconnect   = 8  // Red disconnects
	GameResultBlackDisconnect = 9  // Black disconnects
)

// HistoryItem represents a game in user's history
type HistoryItem struct {
	GameID       string        `json:"game_id"`
	Result       string        `json:"result"`
	MySide       string        `json:"my_side"`
	Opponent     *OpponentInfo `json:"opponent"`
	RatingChange int           `json:"rating_change"`
	TotalMoves   int           `json:"total_moves"`
	PlayedAt     string        `json:"played_at"`
}
