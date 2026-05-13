package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/jerrykong/xiangqi/internal/repository"
)

// MatchService errors
var (
	ErrMatchTimeout = errors.New("match timeout")
	ErrAlreadyInQueue = errors.New("already in match queue")
	ErrNotInQueue     = errors.New("not in match queue")
)

// QueueEntry represents an entry in the match queue
type QueueEntry struct {
	UserID    int64  `json:"user_id"`
	Username  string `json:"username"`
	Rating    int    `json:"rating"`
	SessionID string `json:"ws_session_id"`
	JoinedAt  int64  `json:"joined_at"`
}

// QueueResponse represents a queue join response
type QueueResponse struct {
	Status         string `json:"status"`
	QueueID        string `json:"queue_id"`
	EstimatedWait  int    `json:"estimated_wait"`
}

// MatchService handles ELO-based matchmaking
type MatchService struct {
	redis       *redis.Client
	roomService  *RoomService
	gameProxy    *GameProxy
	eloService   *EloService
	userRepo     *repository.UserRepository
	eloRepo      *repository.EloRepository
	matchCtx     context.Context
	matchCancel  context.CancelFunc
}

// NewMatchService creates a new MatchService
func NewMatchService(
	redisClient *redis.Client,
	roomService *RoomService,
	gameProxy *GameProxy,
	eloService *EloService,
	userRepo *repository.UserRepository,
	eloRepo *repository.EloRepository,
) *MatchService {
	ctx, cancel := context.WithCancel(context.Background())
	return &MatchService{
		redis:      redisClient,
		roomService: roomService,
		gameProxy:   gameProxy,
		eloService:  eloService,
		userRepo:    userRepo,
		eloRepo:     eloRepo,
		matchCtx:    ctx,
		matchCancel: cancel,
	}
}

// StartMatchLoop starts the background match loop
func (s *MatchService) StartMatchLoop() {
	go func() {
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-s.matchCtx.Done():
				return
			case <-ticker.C:
				s.findAndMatch()
			}
		}
	}()
}

// StopMatchLoop stops the match loop
func (s *MatchService) StopMatchLoop() {
	s.matchCancel()
}

// JoinQueue adds a user to the PvP match queue
func (s *MatchService) JoinQueue(ctx context.Context, userID int64) (*QueueResponse, error) {
	// Check if already in queue
	inQueue, err := s.isUserInQueue(ctx, userID)
	if err != nil {
		return nil, err
	}
	if inQueue {
		return nil, ErrAlreadyInQueue
	}

	// Get user info
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Get ELO rating
	elo, err := s.eloRepo.GetOrCreate(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Create queue entry
	entry := &QueueEntry{
		UserID:    userID,
		Username:  user.Username,
		Rating:    elo.Rating,
		SessionID: uuid.New().String(),
		JoinedAt:  time.Now().Unix(),
	}

	// Serialize entry
	data, err := json.Marshal(entry)
	if err != nil {
		return nil, err
	}

	// Add to sorted set (score = ELO rating)
	key := "match:pvp:waiting"
	if err := s.redis.ZAdd(ctx, key, redis.Z{Score: float64(elo.Rating), Member: string(data)}).Err(); err != nil {
		return nil, err
	}

	// Also store by user ID for quick lookup
	userKey := fmt.Sprintf("match:pvp:user:%d", userID)
	if err := s.redis.Set(ctx, userKey, string(data), 10*time.Minute).Err(); err != nil {
		return nil, err
	}

	return &QueueResponse{
		Status:        "queued",
		QueueID:       entry.SessionID,
		EstimatedWait: 30,
	}, nil
}

// LeaveQueue removes a user from the PvP match queue
func (s *MatchService) LeaveQueue(ctx context.Context, userID int64) error {
	// Get user entry
	userKey := fmt.Sprintf("match:pvp:user:%d", userID)
	data, err := s.redis.Get(ctx, userKey).Bytes()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return ErrNotInQueue
		}
		return err
	}

	// Remove from sorted set
	key := "match:pvp:waiting"
	if err := s.redis.ZRem(ctx, key, string(data)).Err(); err != nil {
		return err
	}

	// Remove user key
	if err := s.redis.Del(ctx, userKey).Err(); err != nil {
		return err
	}

	return nil
}

// GetQueueStatus returns the current queue status for a user
func (s *MatchService) GetQueueStatus(ctx context.Context, userID int64) (*QueueStatus, error) {
	// Check if user is in queue
	inQueue, err := s.isUserInQueue(ctx, userID)
	if err != nil {
		return nil, err
	}

	if !inQueue {
		return &QueueStatus{Status: "not_in_queue"}, nil
	}

	// Get queue position
	pos, err := s.getQueuePosition(ctx, userID)
	if err != nil {
		return nil, err
	}

	return &QueueStatus{
		Status:       "queued",
		Position:     pos,
		EstimatedWait: pos * 30,
	}, nil
}

// QueueStatus represents queue status
type QueueStatus struct {
	Status       string `json:"status"`
	Position     int    `json:"position,omitempty"`
	EstimatedWait int    `json:"estimated_wait,omitempty"`
}

// isUserInQueue checks if a user is in the queue
func (s *MatchService) isUserInQueue(ctx context.Context, userID int64) (bool, error) {
	userKey := fmt.Sprintf("match:pvp:user:%d", userID)
	exists, err := s.redis.Exists(ctx, userKey).Result()
	return exists > 0, err
}

// getQueuePosition gets the user's position in the queue
func (s *MatchService) getQueuePosition(ctx context.Context, userID int64) (int, error) {
	userKey := fmt.Sprintf("match:pvp:user:%d", userID)
	data, err := s.redis.Get(ctx, userKey).Bytes()
	if err != nil {
		return 0, err
	}

	// Parse entry
	var entry QueueEntry
	if err := json.Unmarshal(data, &entry); err != nil {
		return 0, err
	}

	// Count players with higher or equal rating (ahead in queue)
	key := "match:pvp:waiting"
	count, err := s.redis.ZCount(ctx, key, "+inf", fmt.Sprintf("%f", float64(entry.Rating))).Result()
	if err != nil {
		return 0, err
	}

	return int(count), nil
}

// findAndMatch attempts to match players in the queue
func (s *MatchService) findAndMatch() {
	ctx := context.Background()

	// Get all waiting players sorted by rating
	key := "match:pvp:waiting"
	entries, err := s.redis.ZRange(ctx, key, 0, -1).Result()
	if err != nil {
		return
	}

	if len(entries) < 2 {
		return
	}

	// Parse entries
	var queueEntries []QueueEntry
	for _, entryStr := range entries {
		var entry QueueEntry
		if err := json.Unmarshal([]byte(entryStr), &entry); err != nil {
			continue
		}
		queueEntries = append(queueEntries, entry)
	}

	// Match players
	used := make(map[int]bool)
	for i := 0; i < len(queueEntries); i++ {
		if used[i] {
			continue
		}

		playerA := queueEntries[i]
		waitTime := time.Now().Unix() - playerA.JoinedAt

		// Get threshold based on rating and wait time
		threshold := s.getMatchThreshold(playerA.Rating, waitTime)

		// Find a match
		for j := i + 1; j < len(queueEntries); j++ {
			if used[j] {
				continue
			}

			playerB := queueEntries[j]
			ratingDiff := abs(playerA.Rating - playerB.Rating)

			if ratingDiff <= threshold {
				// Match found!
				s.createMatch(ctx, &playerA, &playerB)
				used[i] = true
				used[j] = true
				break
			}
		}
	}
}

// getMatchThreshold calculates the rating difference threshold
func (s *MatchService) getMatchThreshold(rating int, waitTime int64) int {
	// Base threshold based on rating
	var baseThreshold int
	if rating < 1200 {
		baseThreshold = 200 // New players
	} else if rating < 1800 {
		baseThreshold = 100
	} else {
		baseThreshold = 150
	}

	// Increase threshold over time
	bonus := int(waitTime/30) * 25 // +25 per 30 seconds
	if bonus > 100 {
		bonus = 100
	}

	return baseThreshold + bonus
}

// createMatch creates a match between two players
func (s *MatchService) createMatch(ctx context.Context, playerA, playerB *QueueEntry) {
	// Remove both from queue
	s.removeFromQueue(ctx, playerA)
	s.removeFromQueue(ctx, playerB)

	// Create room
	room, err := s.roomService.CreateRoom(ctx, playerA.UserID)
	if err != nil {
		return
	}

	// Join second player
	_, err = s.roomService.JoinRoom(ctx, room.RoomID, playerB.UserID)
	if err != nil {
		return
	}

	// Get ELO ratings
	eloA, _ := s.eloRepo.GetOrCreate(ctx, playerA.UserID)
	eloB, _ := s.eloRepo.GetOrCreate(ctx, playerB.UserID)

	// Call game proxy
	assignResp, err := s.gameProxy.AssignGame(ctx, &AssignRequest{
		RoomID:   room.RoomID,
		GameType: "pvp",
		Players: []PlayerInfo{
			{UserID: playerA.UserID, Username: playerA.Username, Side: "red"},
			{UserID: playerB.UserID, Username: playerB.Username, Side: "black"},
		},
	})

	if err != nil {
		return
	}

	// Publish match found event (WebSocket notification would go here)
	s.publishMatchFound(ctx, playerA, playerB, room.RoomID, assignResp.WsURL, assignResp.SessionToken, eloA.Rating, eloB.Rating)
}

// removeFromQueue removes a player from the queue
func (s *MatchService) removeFromQueue(ctx context.Context, entry *QueueEntry) {
	key := "match:pvp:waiting"
	data, _ := json.Marshal(entry)
	s.redis.ZRem(ctx, key, string(data))

	userKey := fmt.Sprintf("match:pvp:user:%d", entry.UserID)
	s.redis.Del(ctx, userKey)
}

// publishMatchFound publishes a match found event
func (s *MatchService) publishMatchFound(ctx context.Context, playerA, playerB *QueueEntry, roomID, wsURL, token string, ratingA, ratingB int) {
	// Publish to Redis for WebSocket servers to consume
	channel := "match:notifications"

	// Notify player A
	msgA := map[string]interface{}{
		"type": "match_found",
		"data": map[string]interface{}{
			"room_id":  roomID,
			"opponent": map[string]interface{}{"user_id": playerB.UserID, "username": playerB.Username, "rating": ratingB},
			"your_side": "red",
			"game_ws_url": wsURL,
			"game_token":  token,
		},
		"user_id": playerA.UserID,
	}
	s.publish(ctx, channel, msgA)

	// Notify player B
	msgB := map[string]interface{}{
		"type": "match_found",
		"data": map[string]interface{}{
			"room_id":  roomID,
			"opponent": map[string]interface{}{"user_id": playerA.UserID, "username": playerA.Username, "rating": ratingA},
			"your_side": "black",
			"game_ws_url": wsURL,
			"game_token":  token,
		},
		"user_id": playerB.UserID,
	}
	s.publish(ctx, channel, msgB)
}

// publish publishes a message to a Redis channel
func (s *MatchService) publish(ctx context.Context, channel string, msg interface{}) {
	data, err := json.Marshal(msg)
	if err != nil {
		return
	}
	s.redis.Publish(ctx, channel, string(data))
}

// abs returns the absolute value
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
