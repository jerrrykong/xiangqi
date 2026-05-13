package service

import (
	"context"
	"errors"
	"time"

	modelpkg "github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/repository"
	"github.com/redis/go-redis/v9"
)

// AdminService handles admin-related operations
type AdminService struct {
	userRepo   *repository.UserRepository
	roomRepo   *repository.RoomRepository
	gameRepo   *repository.GameRepository
	eloRepo    *repository.EloRepository
	modelRepo  *repository.ModelRepository
	matchSvc   *MatchService
	redis      *redis.Client
}

// NewAdminService creates a new AdminService
func NewAdminService(
	userRepo *repository.UserRepository,
	roomRepo *repository.RoomRepository,
	gameRepo *repository.GameRepository,
	eloRepo *repository.EloRepository,
	modelRepo *repository.ModelRepository,
	matchSvc *MatchService,
	redisClient *redis.Client,
) *AdminService {
	return &AdminService{
		userRepo:  userRepo,
		roomRepo:  roomRepo,
		gameRepo:  gameRepo,
		eloRepo:   eloRepo,
		modelRepo: modelRepo,
		matchSvc:  matchSvc,
		redis:     redisClient,
	}
}

// ListUsersOptions represents options for listing users
type ListUsersOptions struct {
	Page     int
	PageSize int
	Search   string
	Banned   *bool
}

// UserListItem represents a user in admin list
type UserListItem struct {
	UserID     int64  `json:"user_id"`
	Username   string `json:"username"`
	Rating     int    `json:"rating"`
	GamesCount int    `json:"games_count"`
	IsBanned   bool   `json:"is_banned"`
	CreatedAt  string `json:"created_at"`
}

// ListUsers lists users with pagination
func (s *AdminService) ListUsers(ctx context.Context, opts *ListUsersOptions) (*UserListResponse, error) {
	if opts.Page < 1 {
		opts.Page = 1
	}
	if opts.PageSize < 1 {
		opts.PageSize = 20
	}

	users, total, err := s.userRepo.List(ctx, opts.Page, opts.PageSize, opts.Search, opts.Banned)
	if err != nil {
		return nil, err
	}

	items := make([]UserListItem, 0, len(users))
	for _, user := range users {
		elo, _ := s.eloRepo.GetOrCreate(ctx, user.ID)
		items = append(items, UserListItem{
			UserID:     user.ID,
			Username:   user.Username,
			Rating:     elo.Rating,
			GamesCount: elo.GamesCount,
			IsBanned:   user.IsBanned,
			CreatedAt:  user.CreatedAt.Format(time.RFC3339),
		})
	}

	return &UserListResponse{
		Total:    total,
		Page:     opts.Page,
		PageSize: opts.PageSize,
		Users:    items,
	}, nil
}

// UserListResponse represents a user list response
type UserListResponse struct {
	Total    int64           `json:"total"`
	Page     int             `json:"page"`
	PageSize int             `json:"page_size"`
	Users    []UserListItem  `json:"users"`
}

// BanUserRequest represents a ban request
type BanUserRequest struct {
	Banned bool   `json:"banned"`
	Reason string `json:"reason"`
}

// BanUser bans or unbans a user
func (s *AdminService) BanUser(ctx context.Context, userID int64, req *BanUserRequest) error {
	// Check if user exists
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return errors.New("user not found")
	}

	// Update ban status
	if err := s.userRepo.SetBanned(ctx, userID, req.Banned); err != nil {
		return err
	}

	// If banning, remove from match queue
	if req.Banned {
		_ = s.matchSvc.LeaveQueue(ctx, userID)
	}

	_ = user // Avoid unused warning

	return nil
}

// StatsResponse represents admin stats response
type StatsResponse struct {
	TotalUsers          int64 `json:"total_users"`
	TotalGames         int64 `json:"total_games"`
	TodayGames          int64 `json:"today_games"`
	OnlineUsers         int64 `json:"online_users"`
	AvgWaitTimeSeconds  int   `json:"avg_wait_time_seconds"`
	AIEloRating         int   `json:"ai_elo_rating"`
}

// GetStats returns admin statistics
func (s *AdminService) GetStats(ctx context.Context) (*StatsResponse, error) {
	// Get user count
	userCount, err := s.userRepo.GetUserCount(ctx)
	if err != nil {
		return nil, err
	}

	// Get total games
	totalGames, err := s.gameRepo.GetTotalGamesCount(ctx)
	if err != nil {
		return nil, err
	}

	// Get today's games
	todayGames, err := s.gameRepo.GetTodayGamesCount(ctx)
	if err != nil {
		return nil, err
	}

	// Get online users from Redis
	onlineUsers := int64(0)
	if s.redis != nil {
		onlineUsers, _ = s.redis.SCard(ctx, "online:users").Result()
	}

	// Get AI rating (latest online model)
	aiElo := 2000 // Default
	if model, err := s.modelRepo.GetLatestOnline(ctx); err == nil && model.EloScore != nil {
		aiElo = *model.EloScore
	}

	return &StatsResponse{
		TotalUsers:         userCount,
		TotalGames:         totalGames,
		TodayGames:         todayGames,
		OnlineUsers:        onlineUsers,
		AvgWaitTimeSeconds: 35, // This should be calculated from actual data
		AIEloRating:        aiElo,
	}, nil
}

// ModelListItem represents a model in admin list
type ModelListItem struct {
	ID        int64             `json:"id"`
	Version   string            `json:"version"`
	Status    modelpkg.ModelStatus `json:"status"`
	EloScore  *int              `json:"elo_score,omitempty"`
	CreatedAt string            `json:"created_at"`
}

// ListModels lists all model versions
func (s *AdminService) ListModels(ctx context.Context) ([]ModelListItem, error) {
	models, err := s.modelRepo.List(ctx)
	if err != nil {
		return nil, err
	}

	items := make([]ModelListItem, 0, len(models))
	for _, m := range models {
		items = append(items, ModelListItem{
			ID:        m.ID,
			Version:   m.Version,
			Status:    m.Status,
			EloScore:  m.EloScore,
			CreatedAt: m.CreatedAt.Format(time.RFC3339),
		})
	}

	return items, nil
}

// PublishModel publishes a model (changes status to online)
func (s *AdminService) PublishModel(ctx context.Context, modelID int64) error {
	m, err := s.modelRepo.GetByID(ctx, modelID)
	if err != nil {
		return errors.New("model not found")
	}

	// Can only publish validating models
	if m.Status != modelpkg.ModelStatusValidating {
		return errors.New("can only publish validating models")
	}

	return s.modelRepo.UpdateStatus(ctx, modelID, modelpkg.ModelStatusOnline)
}
