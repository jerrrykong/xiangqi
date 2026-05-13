// Package jwt provides JWT token generation and validation
package jwt

import (
	"errors"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

var (
	// ErrTokenExpired indicates the token has expired
	ErrTokenExpired = errors.New("token has expired")
	// ErrTokenInvalid indicates the token is invalid
	ErrTokenInvalid = errors.New("token is invalid")
)

// Claims represents JWT claims
type Claims struct {
	UserID   int64  `json:"user_id"`
	Username string `json:"username"`
	IsAdmin  bool   `json:"is_admin"`
	jwt.RegisteredClaims
}

// JWTManager handles JWT operations
type JWTManager struct {
	secretKey   []byte
	expireHours int
}

// NewJWTManager creates a new JWT manager
func NewJWTManager(secret string, expireHours int) *JWTManager {
	return &JWTManager{
		secretKey:   []byte(secret),
		expireHours: expireHours,
	}
}

// GenerateToken generates a new JWT token for a user
func (m *JWTManager) GenerateToken(userID int64, username string, isAdmin bool) (string, time.Time, error) {
	expiresAt := time.Now().Add(time.Duration(m.expireHours) * time.Hour)

	claims := &Claims{
		UserID:   userID,
		Username: username,
		IsAdmin:  isAdmin,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expiresAt),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			NotBefore: jwt.NewNumericDate(time.Now()),
			Issuer:    "xiangqi-web-service",
			Subject:   username,
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(m.secretKey)
	if err != nil {
		return "", time.Time{}, err
	}

	return tokenString, expiresAt, nil
}

// ParseToken parses and validates a JWT token
func (m *JWTManager) ParseToken(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, ErrTokenInvalid
		}
		return m.secretKey, nil
	})

	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, ErrTokenExpired
		}
		return nil, ErrTokenInvalid
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, ErrTokenInvalid
	}

	return claims, nil
}

// RefreshToken refreshes a token and returns a new one
func (m *JWTManager) RefreshToken(claims *Claims) (string, time.Time, error) {
	return m.GenerateToken(claims.UserID, claims.Username, claims.IsAdmin)
}
