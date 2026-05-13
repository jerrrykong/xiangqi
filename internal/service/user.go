// Package service provides business logic layer implementations
package service

import (
	"context"
	"errors"
	"regexp"
	"time"
	"unicode"

	"golang.org/x/crypto/bcrypt"

	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/pkg/jwt"
	"github.com/jerrykong/xiangqi/internal/repository"
)

// Common service errors
var (
	ErrInvalidUsername     = errors.New("invalid username")
	ErrInvalidPassword     = errors.New("invalid password")
	ErrUsernameExists      = errors.New("username already exists")
	ErrInvalidCredentials  = errors.New("invalid credentials")
	ErrUserBanned          = errors.New("user is banned")
)

// RegisterRequest represents a user registration request
type RegisterRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
	Nickname string `json:"nickname"`
}

// LoginRequest represents a user login request
type LoginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

// UpdateProfileRequest represents a profile update request
type UpdateProfileRequest struct {
	Nickname string `json:"nickname"`
	Avatar   string `json:"avatar"`
}

// RankingsRequest represents a rankings query request
type RankingsRequest struct {
	Page     int `form:"page" binding:"min=1"`
	PageSize int `form:"page_size" binding:"min=1,max=100"`
}

// RankingsResponse represents a rankings response
type RankingsResponse struct {
	Total    int64                `json:"total"`
	Page     int                  `json:"page"`
	PageSize int                  `json:"page_size"`
	Rankings []model.RankingItem  `json:"rankings"`
}

// HistoryRequest represents a history query request
type HistoryRequest struct {
	Page     int    `form:"page" binding:"min=1"`
	PageSize int    `form:"page_size" binding:"min=1,max=100"`
	Type     string `form:"type"`
}

// UserService handles user-related business logic
type UserService struct {
	userRepo *repository.UserRepository
	eloRepo  *repository.EloRepository
	gameRepo *repository.GameRepository
	jwtMgr   *jwt.JWTManager
}

// NewUserService creates a new UserService
func NewUserService(
	userRepo *repository.UserRepository,
	eloRepo *repository.EloRepository,
	gameRepo *repository.GameRepository,
	jwtMgr *jwt.JWTManager,
) *UserService {
	return &UserService{
		userRepo: userRepo,
		eloRepo:  eloRepo,
		gameRepo: gameRepo,
		jwtMgr:   jwtMgr,
	}
}

// Register handles user registration
func (s *UserService) Register(ctx context.Context, req *RegisterRequest) (*model.UserProfile, error) {
	// Validate username
	if !isValidUsername(req.Username) {
		return nil, ErrInvalidUsername
	}

	// Validate password
	if !isValidPassword(req.Password) {
		return nil, ErrInvalidPassword
	}

	// Check if username exists
	exists, err := s.userRepo.ExistsUsername(ctx, req.Username)
	if err != nil {
		return nil, err
	}
	if exists {
		return nil, ErrUsernameExists
	}

	// Hash password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	// Create user
	nickname := req.Nickname
	if nickname == "" {
		nickname = req.Username
	}

	user := &model.User{
		Username:     req.Username,
		PasswordHash: string(hashedPassword),
		Nickname:     nickname,
	}

	if err := s.userRepo.Create(ctx, user); err != nil {
		return nil, err
	}

	// Create ELO rating
	elo := &model.EloRating{
		UserID:     user.ID,
		Rating:     model.DefaultEloRating,
		GamesCount: 0,
	}
	if err := s.eloRepo.Create(ctx, elo); err != nil {
		return nil, err
	}

	return &model.UserProfile{
		UserID:     user.ID,
		Username:   user.Username,
		Nickname:   user.Nickname,
		Rating:     elo.Rating,
		GamesCount: elo.GamesCount,
	}, nil
}

// Login handles user login
func (s *UserService) Login(ctx context.Context, req *LoginRequest) (*LoginResponse, error) {
	// Get user by username
	user, err := s.userRepo.GetByUsername(ctx, req.Username)
	if err != nil {
		return nil, ErrInvalidCredentials
	}

	// Check if user is banned
	if user.IsBanned {
		return nil, ErrUserBanned
	}

	// Verify password
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
		return nil, ErrInvalidCredentials
	}

	// Generate JWT token
	token, expiresAt, err := s.jwtMgr.GenerateToken(user.ID, user.Username, user.IsAdmin)
	if err != nil {
		return nil, err
	}

	// Update last login time
	_ = s.userRepo.UpdateLastLogin(ctx, user.ID)

	// Get ELO rating
	elo, err := s.eloRepo.GetOrCreate(ctx, user.ID)
	if err != nil {
		return nil, err
	}

	return &LoginResponse{
		UserID:     user.ID,
		Username:   user.Username,
		Nickname:   user.Nickname,
		Rating:     elo.Rating,
		GamesCount: elo.GamesCount,
		Token:      token,
		ExpiresAt:  expiresAt.Format(time.RFC3339),
	}, nil
}

// LoginResponse represents a login response
type LoginResponse struct {
	UserID     int64  `json:"user_id"`
	Username   string `json:"username"`
	Nickname   string `json:"nickname"`
	Rating     int    `json:"rating"`
	GamesCount int    `json:"games_count"`
	Token      string `json:"token"`
	ExpiresAt  string `json:"expires_at"`
}

// RefreshToken refreshes a user's JWT token
func (s *UserService) RefreshToken(ctx context.Context, claims *jwt.Claims) (*LoginResponse, error) {
	// Get user
	user, err := s.userRepo.GetByID(ctx, claims.UserID)
	if err != nil {
		return nil, ErrInvalidCredentials
	}

	// Check if user is banned
	if user.IsBanned {
		return nil, ErrUserBanned
	}

	// Generate new token
	token, expiresAt, err := s.jwtMgr.RefreshToken(claims)
	if err != nil {
		return nil, err
	}

	// Get ELO rating
	elo, err := s.eloRepo.GetOrCreate(ctx, user.ID)
	if err != nil {
		return nil, err
	}

	return &LoginResponse{
		UserID:     user.ID,
		Username:   user.Username,
		Nickname:   user.Nickname,
		Rating:     elo.Rating,
		GamesCount: elo.GamesCount,
		Token:      token,
		ExpiresAt:  expiresAt.Format(time.RFC3339),
	}, nil
}

// GetUser retrieves a user by ID
func (s *UserService) GetUser(ctx context.Context, userID int64) (*model.UserProfile, error) {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return nil, ErrInvalidCredentials
	}

	elo, err := s.eloRepo.GetOrCreate(ctx, userID)
	if err != nil {
		return nil, err
	}

	return &model.UserProfile{
		UserID:     user.ID,
		Username:   user.Username,
		Nickname:   user.Nickname,
		Avatar:     user.Avatar,
		Rating:     elo.Rating,
		GamesCount: elo.GamesCount,
		CreatedAt:  user.CreatedAt.Format(time.RFC3339),
	}, nil
}

// UpdateProfile updates a user's profile
func (s *UserService) UpdateProfile(ctx context.Context, userID int64, req *UpdateProfileRequest) error {
	return s.userRepo.UpdateProfile(ctx, userID, req.Nickname, req.Avatar)
}

// GetRankings retrieves the rankings
func (s *UserService) GetRankings(ctx context.Context, req *RankingsRequest) (*RankingsResponse, error) {
	if req.Page < 1 {
		req.Page = 1
	}
	if req.PageSize < 1 {
		req.PageSize = 20
	}
	if req.PageSize > 100 {
		req.PageSize = 100
	}

	rankings, total, err := s.eloRepo.GetRankings(ctx, req.Page, req.PageSize)
	if err != nil {
		return nil, err
	}

	return &RankingsResponse{
		Total:    total,
		Page:     req.Page,
		PageSize: req.PageSize,
		Rankings: rankings,
	}, nil
}

// GetHistory retrieves a user's game history
func (s *UserService) GetHistory(ctx context.Context, userID int64, req *HistoryRequest) (*HistoryResponse, error) {
	if req.Page < 1 {
		req.Page = 1
	}
	if req.PageSize < 1 {
		req.PageSize = 20
	}

	games, total, err := s.gameRepo.GetUserHistory(ctx, userID, req.Page, req.PageSize, req.Type)
	if err != nil {
		return nil, err
	}

	// Build history items
	items := make([]model.HistoryItem, 0, len(games))
	for _, game := range games {
		var mySide string
		var opponentID int64
		if game.RedUserID == userID {
			mySide = "red"
			opponentID = game.BlackUserID
		} else {
			mySide = "black"
			opponentID = game.RedUserID
		}

		// Get opponent info
		var opponent *model.OpponentInfo
		if opponentID > 0 {
			if oppUser, err := s.userRepo.GetByID(ctx, opponentID); err == nil {
				if oppElo, err := s.eloRepo.GetByUserID(ctx, opponentID); err == nil {
					opponent = &model.OpponentInfo{
						UserID:   oppUser.ID,
						Username: oppUser.Username,
						Rating:   oppElo.Rating,
					}
				}
			}
		}

		// Get rating change
		var ratingChange int
		if histories, _, err := s.eloRepo.GetHistory(ctx, userID, 1, 100); err == nil {
			for _, h := range histories {
				if h.GameID == game.ID {
					ratingChange = h.Change
					break
				}
			}
		}

		result := "loss"
		if (game.Winner == "red" && mySide == "red") || (game.Winner == "black" && mySide == "black") {
			result = "win"
		} else if game.Winner == "draw" {
			result = "draw"
		}

		items = append(items, model.HistoryItem{
			GameID:   game.RoomID,
			Result:   result,
			MySide:   mySide,
			Opponent: opponent,
			RatingChange: ratingChange,
			TotalMoves: game.TotalMoves,
			PlayedAt: game.EndTime.Format(time.RFC3339),
		})
	}

	return &HistoryResponse{
		Total:   total,
		History: items,
	}, nil
}

// HistoryResponse represents a history response
type HistoryResponse struct {
	Total   int64                `json:"total"`
	History []model.HistoryItem   `json:"history"`
}

// isValidUsername validates username format
func isValidUsername(username string) bool {
	if len(username) < 4 || len(username) > 32 {
		return false
	}
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_]+$`, username)
	return matched
}

// isValidPassword validates password format
func isValidPassword(password string) bool {
	if len(password) < 8 {
		return false
	}

	var hasLetter, hasNumber bool
	for _, c := range password {
		if unicode.IsLetter(c) {
			hasLetter = true
		}
		if unicode.IsNumber(c) {
			hasNumber = true
		}
	}
	return hasLetter && hasNumber
}
