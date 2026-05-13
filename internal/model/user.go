// Package model contains data models for the web service
package model

import (
	"time"
)

// User represents a user in the system
type User struct {
	ID           int64      `json:"id" gorm:"primaryKey;autoIncrement"`
	Username     string     `json:"username" gorm:"type:varchar(32);uniqueIndex;not null"`
	PasswordHash string     `json:"-" gorm:"column:password_hash;type:varchar(255);not null"`
	Nickname     string     `json:"nickname" gorm:"type:varchar(64)"`
	Avatar       string     `json:"avatar" gorm:"type:varchar(255)"`
	IsAdmin      bool       `json:"is_admin" gorm:"default:false"`
	IsBanned     bool       `json:"is_banned" gorm:"default:false"`
	CreatedAt    time.Time  `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt    time.Time  `json:"updated_at" gorm:"autoUpdateTime"`
	LastLoginAt  *time.Time `json:"last_login_at,omitempty"`
}

// TableName returns the table name for User
func (User) TableName() string {
	return "users"
}

// UserProfile represents user profile with ELO rating
type UserProfile struct {
	UserID     int64  `json:"user_id"`
	Username   string `json:"username"`
	Nickname   string `json:"nickname"`
	Avatar     string `json:"avatar,omitempty"`
	Rating     int    `json:"rating"`
	GamesCount int    `json:"games_count"`
	CreatedAt  string `json:"created_at,omitempty"`
}

// RankingItem represents a user in the ranking list
type RankingItem struct {
	Rank       int    `json:"rank"`
	UserID     int64  `json:"user_id"`
	Username   string `json:"username"`
	Nickname   string `json:"nickname,omitempty"`
	Rating     int    `json:"rating"`
	GamesCount int    `json:"games_count"`
}
