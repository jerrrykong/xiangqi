// Package repository provides data access layer implementations
package repository

import (
	"context"
	"time"

	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
)

// UserRepository handles user data access
type UserRepository struct {
	db *gorm.DB
}

// NewUserRepository creates a new UserRepository
func NewUserRepository(db *gorm.DB) *UserRepository {
	return &UserRepository{db: db}
}

// Create creates a new user
func (r *UserRepository) Create(ctx context.Context, user *model.User) error {
	return r.db.WithContext(ctx).Create(user).Error
}

// GetByID retrieves a user by ID
func (r *UserRepository) GetByID(ctx context.Context, id int64) (*model.User, error) {
	var user model.User
	err := r.db.WithContext(ctx).First(&user, id).Error
	if err != nil {
		return nil, err
	}
	return &user, nil
}

// GetByUsername retrieves a user by username
func (r *UserRepository) GetByUsername(ctx context.Context, username string) (*model.User, error) {
	var user model.User
	err := r.db.WithContext(ctx).Where("username = ?", username).First(&user).Error
	if err != nil {
		return nil, err
	}
	return &user, nil
}

// Update updates a user
func (r *UserRepository) Update(ctx context.Context, user *model.User) error {
	return r.db.WithContext(ctx).Save(user).Error
}

// UpdateLastLogin updates the last login time for a user
func (r *UserRepository) UpdateLastLogin(ctx context.Context, userID int64) error {
	now := time.Now()
	return r.db.WithContext(ctx).Model(&model.User{}).Where("id = ?", userID).Update("last_login_at", &now).Error
}

// UpdateProfile updates user profile (nickname, avatar)
func (r *UserRepository) UpdateProfile(ctx context.Context, userID int64, nickname, avatar string) error {
	updates := map[string]interface{}{}
	if nickname != "" {
		updates["nickname"] = nickname
	}
	if avatar != "" {
		updates["avatar"] = avatar
	}
	return r.db.WithContext(ctx).Model(&model.User{}).Where("id = ?", userID).Updates(updates).Error
}

// SetBanned sets the banned status for a user
func (r *UserRepository) SetBanned(ctx context.Context, userID int64, banned bool) error {
	return r.db.WithContext(ctx).Model(&model.User{}).Where("id = ?", userID).Update("is_banned", banned).Error
}

// List lists users with pagination and filters
func (r *UserRepository) List(ctx context.Context, page, pageSize int, search string, banned *bool) ([]model.User, int64, error) {
	var users []model.User
	var total int64

	query := r.db.WithContext(ctx).Model(&model.User{})

	if search != "" {
		query = query.Where("username LIKE ?", "%"+search+"%")
	}
	if banned != nil {
		query = query.Where("is_banned = ?", *banned)
	}

	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	if err := query.Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&users).Error; err != nil {
		return nil, 0, err
	}

	return users, total, nil
}

// ExistsUsername checks if a username already exists
func (r *UserRepository) ExistsUsername(ctx context.Context, username string) (bool, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&model.User{}).Where("username = ?", username).Count(&count).Error
	return count > 0, err
}

// GetUserCount returns the total number of users
func (r *UserRepository) GetUserCount(ctx context.Context) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&model.User{}).Count(&count).Error
	return count, err
}
