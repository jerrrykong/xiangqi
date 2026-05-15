package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"github.com/jerrykong/xiangqi/internal/pkg/log"
)

// GameProxy handles communication with the Game service
type GameProxy struct {
	client      *http.Client
	baseURL     string
	secret      string
	callbackURL string
	redis       *redis.Client
}

// AssignRequest represents a game assignment request
type AssignRequest struct {
	RoomID      string       `json:"room_id"`
	GameType    string       `json:"game_type"` // "pvp" / "pve"
	Players     []PlayerInfo `json:"players"`
	Difficulty  *int         `json:"difficulty,omitempty"`
	CallbackURL string       `json:"callback_url"`
}

// PlayerInfo represents player information for game assignment
type PlayerInfo struct {
	UserID     int64  `json:"user_id"`
	Username   string `json:"username"`
	Side       string `json:"side"` // "red" / "black"
	WSSession  string `json:"ws_session,omitempty"`
}

// AssignResponse represents a game assignment response
type AssignResponse struct {
	RoomID       string `json:"room_id"`
	WsURL        string `json:"ws_url"`
	GameID       string `json:"game_id"`
	SessionToken string `json:"session_token"`
}

// SessionInfo represents session information stored in Redis
type SessionInfo struct {
	RoomID       string `json:"room_id"`
	WsURL        string `json:"ws_url"`
	SessionToken string `json:"session_token"`
	GameID       string `json:"game_id"`
}

// NewGameProxy creates a new GameProxy
func NewGameProxy(baseURL, secret, callbackURL string, redisClient *redis.Client) *GameProxy {
	return &GameProxy{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL:     baseURL,
		secret:      secret,
		callbackURL: callbackURL,
		redis:       redisClient,
	}
}

// AssignGame requests the Game service to assign a game
func (p *GameProxy) AssignGame(ctx context.Context, req *AssignRequest) (*AssignResponse, error) {
	start := time.Now()

	// Log request details
	playerIDs := make([]int64, len(req.Players))
	playerSides := make([]string, len(req.Players))
	for i, player := range req.Players {
		playerIDs[i] = player.UserID
		playerSides[i] = player.Side
	}

	log.Info("game_proxy_assign_request",
		"room_id", req.RoomID,
		"game_type", req.GameType,
		"player_ids", playerIDs,
		"player_sides", playerSides,
		"difficulty", req.Difficulty,
	)

	if req.CallbackURL == "" {
		req.CallbackURL = p.callbackURL
	}

	body, err := json.Marshal(req)
	if err != nil {
		log.Error("game_proxy_assign_error",
			"room_id", req.RoomID,
			"step", "marshal_request",
			"error", err.Error(),
		)
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", p.baseURL+"/internal/game/assign", bytes.NewReader(body))
	if err != nil {
		log.Error("game_proxy_assign_error",
			"room_id", req.RoomID,
			"step", "create_request",
			"error", err.Error(),
		)
		return nil, err
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-Internal-Key", p.secret)

	log.Debug("game_proxy_assign_sending",
		"room_id", req.RoomID,
		"url", p.baseURL+"/internal/game/assign",
	)

	resp, err := p.client.Do(httpReq)
	if err != nil {
		log.Error("game_proxy_assign_error",
			"room_id", req.RoomID,
			"step", "http_request",
			"error", err.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		return nil, err
	}
	defer resp.Body.Close()

	log.Debug("game_proxy_assign_response",
		"room_id", req.RoomID,
		"status_code", resp.StatusCode,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	if resp.StatusCode != http.StatusOK {
		errMsg := fmt.Errorf("game service returned status %d", resp.StatusCode)
		log.Error("game_proxy_assign_error",
			"room_id", req.RoomID,
			"step", "check_status",
			"status_code", resp.StatusCode,
			"error", errMsg.Error(),
			"duration_ms", time.Since(start).Milliseconds(),
		)
		return nil, errMsg
	}

	var assignResp AssignResponse
	if err := json.NewDecoder(resp.Body).Decode(&assignResp); err != nil {
		log.Error("game_proxy_assign_error",
			"room_id", req.RoomID,
			"step", "decode_response",
			"error", err.Error(),
		)
		return nil, err
	}

	log.Info("game_proxy_assign_success",
		"room_id", req.RoomID,
		"game_id", assignResp.GameID,
		"ws_url", assignResp.WsURL,
		"duration_ms", time.Since(start).Milliseconds(),
	)

	// Store session info in Redis for later retrieval
	if p.redis != nil {
		sessionInfo := SessionInfo{
			RoomID:       req.RoomID,
			WsURL:        assignResp.WsURL,
			SessionToken: assignResp.SessionToken,
			GameID:       assignResp.GameID,
		}
		if err := p.StoreSession(ctx, req.RoomID, &sessionInfo); err != nil {
			log.Error("game_proxy_assign_store_session_error",
				"room_id", req.RoomID,
				"error", err.Error(),
			)
			// Don't fail the assignment if Redis storage fails
		}
	}

	return &assignResp, nil
}

// StoreSession stores session information in Redis
func (p *GameProxy) StoreSession(ctx context.Context, roomID string, info *SessionInfo) error {
	if p.redis == nil {
		return nil
	}

	data, err := json.Marshal(info)
	if err != nil {
		return err
	}

	key := fmt.Sprintf("game:session:%s", roomID)
	// Session expires in 24 hours
	return p.redis.Set(ctx, key, data, 24*time.Hour).Err()
}

// GetSession retrieves session information from Redis
func (p *GameProxy) GetSession(ctx context.Context, roomID string) (*SessionInfo, error) {
	if p.redis == nil {
		return nil, fmt.Errorf("redis not available")
	}

	key := fmt.Sprintf("game:session:%s", roomID)
	data, err := p.redis.Get(ctx, key).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, nil
		}
		return nil, err
	}

	var info SessionInfo
	if err := json.Unmarshal(data, &info); err != nil {
		return nil, err
	}

	return &info, nil
}

// HandleGameResult handles game result callback from Game service
func (p *GameProxy) HandleGameResult(c *gin.Context) {
	var req GameResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Error("game_proxy_handle_result_bad_request",
			"error", err.Error(),
		)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	log.Info("game_proxy_handle_result",
		"room_id", req.RoomID,
		"result", req.Result,
		"winner", req.Winner,
	)

	// The handler should be registered with the server
	// This method is a placeholder for the actual handler
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}
