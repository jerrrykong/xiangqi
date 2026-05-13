package service

import (
	"context"
	"math"

	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/repository"
)

// EloService handles ELO rating calculations
type EloService struct {
	eloRepo  *repository.EloRepository
	gameRepo *repository.GameRepository
}

// NewEloService creates a new EloService
func NewEloService(eloRepo *repository.EloRepository, gameRepo *repository.GameRepository) *EloService {
	return &EloService{
		eloRepo:  eloRepo,
		gameRepo: gameRepo,
	}
}

// CalculateElo calculates ELO rating changes
// result: 1.0 = win, 0.0 = loss, 0.5 = draw
func (s *EloService) CalculateElo(rA, rB int, result float32) (changeA, changeB int) {
	// Determine K-factor based on games count
	gamesA := s.getGamesCountFromRating(rA)
	K := 40.0
	if gamesA > 100 {
		K = 10.0
	} else if gamesA > 30 {
		K = 20.0
	}

	// Calculate expected score
	EA := 1.0 / (1.0 + math.Pow(10, float64(rB-rA)/400))
	changeA = int(K * (float64(result) - EA))

	// For player B, result is opposite
	EB := 1.0 / (1.0 + math.Pow(10, float64(rA-rB)/400))
	changeB = int(K * ((1.0 - float64(result)) - EB))

	return changeA, changeB
}

// getGamesCountFromRating estimates games count from rating
// This is a rough estimate - in practice, you'd store this separately
func (s *EloService) getGamesCountFromRating(rating int) int {
	// Estimate based on rating (assuming starting at 1500)
	diff := rating - model.DefaultEloRating
	if diff > 0 {
		// Winning players have more games on average
		return 50 + diff/10
	}
	return 50 + diff/10
}

// UpdateRatings updates ratings for both players after a game
func (s *EloService) UpdateRatings(ctx context.Context, redID, blackID int64, result int) error {
	// Get current ratings
	redElo, err := s.eloRepo.GetByUserID(ctx, redID)
	if err != nil {
		return err
	}

	blackElo, err := s.eloRepo.GetByUserID(ctx, blackID)
	if err != nil {
		return err
	}

	// Determine game result for red
	var redResult float32
	switch result {
	case model.GameResultRedWins, model.GameResultRedResign, model.GameResultBlackTimeout, model.GameResultBlackDisconnect:
		redResult = 1.0
	case model.GameResultBlackWins, model.GameResultBlackResign, model.GameResultRedTimeout, model.GameResultRedDisconnect:
		redResult = 0.0
	default:
		redResult = 0.5
	}

	// Calculate changes
	changeRed, changeBlack := s.CalculateElo(redElo.Rating, blackElo.Rating, redResult)

	// Update ratings
	newRedRating := redElo.Rating + changeRed
	newBlackRating := blackElo.Rating + changeBlack

	if err := s.eloRepo.UpdateRating(ctx, redID, newRedRating, redElo.GamesCount+1); err != nil {
		return err
	}

	if err := s.eloRepo.UpdateRating(ctx, blackID, newBlackRating, blackElo.GamesCount+1); err != nil {
		return err
	}

	return nil
}

// ProcessGameResult processes a game result and updates ratings
func (s *EloService) ProcessGameResult(ctx context.Context, gameResult *GameResultRequest) error {
	// Determine winner string (for potential future use)
	var winner string
	switch gameResult.Result {
	case model.GameResultRedWins, model.GameResultRedResign, model.GameResultBlackTimeout, model.GameResultBlackDisconnect:
		winner = "red"
	case model.GameResultBlackWins, model.GameResultBlackResign, model.GameResultRedTimeout, model.GameResultRedDisconnect:
		winner = "black"
	default:
		winner = "draw"
	}
	_ = winner // winner determined but stored for potential logging

	// Update room status
	// Note: This should be called from the caller, not here

	// Update ratings if PvP
	if gameResult.RedUserID > 0 && gameResult.BlackUserID > 0 {
		if err := s.UpdateRatings(ctx, gameResult.RedUserID, gameResult.BlackUserID, gameResult.Result); err != nil {
			return err
		}
	}

	return nil
}

// GameResultRequest represents a game result from Game service
type GameResultRequest struct {
	RoomID      string `json:"room_id"`
	GameID      string `json:"game_id"`
	Result      int    `json:"result"`
	Winner      string `json:"winner"`
	RedUserID   int64  `json:"red_user_id"`
	BlackUserID int64  `json:"black_user_id"`
	TotalMoves  int    `json:"total_moves"`
	Duration    int    `json:"duration_seconds"`
	PvELevel    *int   `json:"pve_level,omitempty"`
}

// GetUserRating gets a user's current rating
func (s *EloService) GetUserRating(ctx context.Context, userID int64) (int, error) {
	elo, err := s.eloRepo.GetOrCreate(ctx, userID)
	if err != nil {
		return 0, err
	}
	return elo.Rating, nil
}

// ValidateRatingChange validates that a rating change is within expected bounds
func ValidateRatingChange(rating, change int) bool {
	absChange := int(math.Abs(float64(change)))
	// Normal rating changes should be within reasonable bounds
	return absChange <= 50
}
