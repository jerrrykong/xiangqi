package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// GameProxy handles communication with the Game service
type GameProxy struct {
	client    *http.Client
	baseURL   string
	secret    string
	callbackURL string
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
	RoomID        string `json:"room_id"`
	WsURL         string `json:"ws_url"`
	GameID        string `json:"game_id"`
	SessionToken  string `json:"session_token"`
}

// NewGameProxy creates a new GameProxy
func NewGameProxy(baseURL, secret, callbackURL string) *GameProxy {
	return &GameProxy{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL:    baseURL,
		secret:     secret,
		callbackURL: callbackURL,
	}
}

// AssignGame requests the Game service to assign a game
func (p *GameProxy) AssignGame(ctx context.Context, req *AssignRequest) (*AssignResponse, error) {
	if req.CallbackURL == "" {
		req.CallbackURL = p.callbackURL
	}

	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", p.baseURL+"/internal/game/assign", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-Internal-Key", p.secret)

	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("game service returned status %d", resp.StatusCode)
	}

	var assignResp AssignResponse
	if err := json.NewDecoder(resp.Body).Decode(&assignResp); err != nil {
		return nil, err
	}

	return &assignResp, nil
}

// HandleGameResult handles game result callback from Game service
func (p *GameProxy) HandleGameResult(c *gin.Context) {
	var req GameResultRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// The handler should be registered with the server
	// This method is a placeholder for the actual handler
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}
