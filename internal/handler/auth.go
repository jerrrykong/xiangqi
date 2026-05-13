// Package handler provides HTTP handler implementations
package handler

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/jerrykong/xiangqi/internal/middleware"
	"github.com/jerrykong/xiangqi/internal/pkg/jwt"
	"github.com/jerrykong/xiangqi/internal/pkg/response"
	"github.com/jerrykong/xiangqi/internal/service"
	"github.com/jerrykong/xiangqi/shared"
)

// AuthHandler handles authentication endpoints
type AuthHandler struct {
	userSvc *service.UserService
}

// NewAuthHandler creates a new AuthHandler
func NewAuthHandler(userSvc *service.UserService) *AuthHandler {
	return &AuthHandler{userSvc: userSvc}
}

// Register handles user registration
// POST /auth/register
func (h *AuthHandler) Register(c *gin.Context) {
	var req service.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	profile, err := h.userSvc.Register(c.Request.Context(), &req)
	if err != nil {
		switch {
		case errors.Is(err, service.ErrInvalidUsername):
			response.Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, "username must be 4-32 characters, letters/numbers/underscore only")
		case errors.Is(err, service.ErrInvalidPassword):
			response.Fail(c, http.StatusBadRequest, shared.ErrCodeInvalidParam, "password must be at least 8 characters with letters and numbers")
		case errors.Is(err, service.ErrUsernameExists):
			response.Fail(c, http.StatusConflict, shared.ErrCodeUserExists, "username already exists")
		default:
			response.InternalError(c)
		}
		return
	}

	response.OK(c, profile)
}

// Login handles user login
// POST /auth/login
func (h *AuthHandler) Login(c *gin.Context) {
	var req service.LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	resp, err := h.userSvc.Login(c.Request.Context(), &req)
	if err != nil {
		switch {
		case errors.Is(err, service.ErrInvalidCredentials):
			response.Fail(c, http.StatusUnauthorized, shared.ErrCodeWrongPassword, "invalid username or password")
		case errors.Is(err, service.ErrUserBanned):
			response.Fail(c, http.StatusForbidden, shared.ErrCodeUserBanned, "user is banned")
		default:
			response.InternalError(c)
		}
		return
	}

	response.OK(c, resp)
}

// Refresh handles token refresh
// POST /auth/refresh
func (h *AuthHandler) Refresh(c *gin.Context) {
	userID := middleware.GetUserID(c)
	username := middleware.GetUsername(c)
	isAdmin := middleware.IsAdmin(c)

	claims := &jwt.Claims{
		UserID:   userID,
		Username: username,
		IsAdmin:  isAdmin,
	}

	resp, err := h.userSvc.RefreshToken(c.Request.Context(), claims)
	if err != nil {
		response.InternalError(c)
		return
	}

	response.OK(c, resp)
}
