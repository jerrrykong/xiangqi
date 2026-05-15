package model

import (
	"database/sql"
	"time"
)

// RoomType represents the type of room (PvP or PvE)
type RoomType string

const (
	RoomTypePvP RoomType = "pvp" // Player vs Player
	RoomTypePvE RoomType = "pve" // Player vs AI
)

// RoomStatus represents the current status of a room
type RoomStatus string

const (
	RoomStatusWaiting  RoomStatus = "waiting"  // Waiting for players
	RoomStatusReady    RoomStatus = "ready"    // Players ready
	RoomStatusPlaying  RoomStatus = "playing"  // Game in progress
	RoomStatusFinished RoomStatus = "finished" // Game finished
)

// Room represents a game room
type Room struct {
	ID          string        `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	Type        RoomType      `json:"type" gorm:"type:varchar(8);not null"`
	Status      RoomStatus    `json:"status" gorm:"type:varchar(16);not null;default:'waiting'"`
	Difficulty  sql.NullInt32 `json:"difficulty,omitempty" gorm:"type:int"`       // PvE difficulty
	RedUserID   sql.NullInt64 `json:"red_user_id,omitempty" gorm:"type:bigint"`   // Red player ID
	BlackUserID sql.NullInt64 `json:"black_user_id,omitempty" gorm:"type:bigint"` // Black player ID
	RedReady    bool          `json:"red_ready" gorm:"default:false"`
	BlackReady  bool          `json:"black_ready" gorm:"default:false"`
	Winner      sql.NullString `json:"winner,omitempty" gorm:"type:varchar(8)"`
	GameID      sql.NullString `json:"game_id,omitempty" gorm:"type:uuid"`        // Game service assigned game ID
	CreatedBy   int64          `json:"created_by" gorm:"type:bigint;not null"`
	CreatedAt   time.Time      `json:"created_at" gorm:"autoCreateTime"`
	StartedAt   *time.Time    `json:"started_at,omitempty"`
	EndedAt     *time.Time    `json:"ended_at,omitempty"`
}

// TableName returns the table name for Room
func (Room) TableName() string {
	return "rooms"
}

// RoomListItem represents a room in the waiting list
type RoomListItem struct {
	RoomID    string `json:"room_id"`
	CreatedBy int64  `json:"created_by"`
	Username  string `json:"username"`
	CreatedAt string `json:"created_at"`
}

// JoinRoomResponse represents the response when joining a room
type JoinRoomResponse struct {
	RoomID    string        `json:"room_id"`
	YourSide  string        `json:"your_side"`
	Opponent  *OpponentInfo `json:"opponent,omitempty"`
	Status    RoomStatus    `json:"status"`
}

// OpponentInfo contains opponent information
type OpponentInfo struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	Rating   int    `json:"rating,omitempty"`
}

// ReadyResponse represents the response when a player is ready
type ReadyResponse struct {
	RoomID      string     `json:"room_id"`
	RedReady    bool       `json:"red_ready"`
	BlackReady  bool       `json:"black_ready"`
	GameStarted bool       `json:"game_started"`
	GameWsURL   string     `json:"game_ws_url,omitempty"`
	GameToken   string     `json:"game_token,omitempty"`
}

// CreateRoomResponse represents the response when creating a room
type CreateRoomResponse struct {
	RoomID    string     `json:"room_id"`
	RoomType  RoomType   `json:"room_type"`
	Status    RoomStatus `json:"status"`
	CreatedAt string     `json:"created_at"`
}

// RoomUserInfo contains a player's info within a room detail response
type RoomUserInfo struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	Rating   int    `json:"rating,omitempty"`
}

// RoomDetailResponse is the full room detail returned by GET /rooms/:id
type RoomDetailResponse struct {
	RoomID     string        `json:"room_id"`
	Status     RoomStatus    `json:"status"`
	Type       RoomType      `json:"type"`
	RedUser    *RoomUserInfo `json:"red_user,omitempty"`
	BlackUser  *RoomUserInfo `json:"black_user,omitempty"`
	RedReady   bool          `json:"red_ready"`
	BlackReady bool          `json:"black_ready"`
	GameWsURL  string        `json:"game_ws_url,omitempty"`
	GameToken  string        `json:"game_token,omitempty"`
	YourSide   string        `json:"your_side,omitempty"`
}
