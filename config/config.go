// Package config provides configuration loading for the web service
package config

import (
	"os"
	"strconv"
	"time"

	"github.com/joho/godotenv"
	"gopkg.in/yaml.v3"
)

// Config is the root configuration structure
type Config struct {
	Server      ServerConfig      `yaml:"server"`
	Database    DatabaseConfig    `yaml:"database"`
	Redis       RedisConfig       `yaml:"redis"`
	JWT         JWTConfig         `yaml:"jwt"`
	Internal    InternalConfig    `yaml:"internal"`
	GameService GameServiceConfig `yaml:"game_service"`
}

// ServerConfig holds HTTP server settings
type ServerConfig struct {
	Host string `yaml:"host"`
	Port int    `yaml:"port"`
}

// DatabaseConfig holds PostgreSQL connection settings
type DatabaseConfig struct {
	Host         string `yaml:"host"`
	Port         int    `yaml:"port"`
	User         string `yaml:"user"`
	Password     string `yaml:"password"`
	DBName       string `yaml:"dbname"`
	MaxOpenConns int    `yaml:"max_open_conns"`
	MaxIdleConns int    `yaml:"max_idle_conns"`
}

// RedisConfig holds Redis connection settings
type RedisConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	Password string `yaml:"password"`
	DB       int    `yaml:"db"`
	PoolSize int    `yaml:"pool_size"`
}

// JWTConfig holds JWT settings
type JWTConfig struct {
	Secret      string `yaml:"secret"`
	ExpireHours int    `yaml:"expire_hours"`
}

// InternalConfig holds internal service settings
type InternalConfig struct {
	Secret string `yaml:"secret"`
}

// GameServiceConfig holds Game service connection settings
type GameServiceConfig struct {
	BaseURL string `yaml:"base_url"`
}

// Load loads configuration from file and environment variables
func Load(path string) (*Config, error) {
	cfg := &Config{}

	// Try to load from YAML file first
	if path != "" {
		data, err := os.ReadFile(path)
		if err == nil {
			if err := yaml.Unmarshal(data, cfg); err != nil {
				return nil, err
			}
		}
	}

	// Load from .env file if exists
	_ = godotenv.Load()

	// Override with environment variables
	cfg.loadFromEnv()

	// Set defaults
	cfg.setDefaults()

	return cfg, nil
}

// loadFromEnv loads configuration from environment variables
func (c *Config) loadFromEnv() {
	// Server
	if v := os.Getenv("SERVER_HOST"); v != "" {
		c.Server.Host = v
	}
	if v := os.Getenv("SERVER_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			c.Server.Port = port
		}
	}

	// Database
	if v := os.Getenv("DB_HOST"); v != "" {
		c.Database.Host = v
	}
	if v := os.Getenv("DB_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			c.Database.Port = port
		}
	}
	if v := os.Getenv("DB_USER"); v != "" {
		c.Database.User = v
	}
	if v := os.Getenv("DB_PASSWORD"); v != "" {
		c.Database.Password = v
	}
	if v := os.Getenv("DB_NAME"); v != "" {
		c.Database.DBName = v
	}
	if v := os.Getenv("DB_MAX_OPEN_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			c.Database.MaxOpenConns = n
		}
	}
	if v := os.Getenv("DB_MAX_IDLE_CONNS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			c.Database.MaxIdleConns = n
		}
	}

	// Redis
	if v := os.Getenv("REDIS_HOST"); v != "" {
		c.Redis.Host = v
	}
	if v := os.Getenv("REDIS_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			c.Redis.Port = port
		}
	}
	if v := os.Getenv("REDIS_PASSWORD"); v != "" {
		c.Redis.Password = v
	}
	if v := os.Getenv("REDIS_DB"); v != "" {
		if db, err := strconv.Atoi(v); err == nil {
			c.Redis.DB = db
		}
	}
	if v := os.Getenv("REDIS_POOL_SIZE"); v != "" {
		if size, err := strconv.Atoi(v); err == nil {
			c.Redis.PoolSize = size
		}
	}

	// JWT
	if v := os.Getenv("JWT_SECRET"); v != "" {
		c.JWT.Secret = v
	}
	if v := os.Getenv("JWT_EXPIRE_HOURS"); v != "" {
		if hours, err := strconv.Atoi(v); err == nil {
			c.JWT.ExpireHours = hours
		}
	}

	// Internal
	if v := os.Getenv("INTERNAL_SECRET"); v != "" {
		c.Internal.Secret = v
	}

	// Game Service
	if v := os.Getenv("GAME_SERVICE_URL"); v != "" {
		c.GameService.BaseURL = v
	}
}

// setDefaults sets default values for configuration
func (c *Config) setDefaults() {
	// Server defaults
	if c.Server.Host == "" {
		c.Server.Host = "0.0.0.0"
	}
	if c.Server.Port == 0 {
		c.Server.Port = 8080
	}

	// Database defaults
	if c.Database.Host == "" {
		c.Database.Host = "localhost"
	}
	if c.Database.Port == 0 {
		c.Database.Port = 5432
	}
	if c.Database.MaxOpenConns == 0 {
		c.Database.MaxOpenConns = 50
	}
	if c.Database.MaxIdleConns == 0 {
		c.Database.MaxIdleConns = 10
	}

	// Redis defaults
	if c.Redis.Host == "" {
		c.Redis.Host = "localhost"
	}
	if c.Redis.Port == 0 {
		c.Redis.Port = 6379
	}
	if c.Redis.PoolSize == 0 {
		c.Redis.PoolSize = 100
	}

	// JWT defaults
	if c.JWT.Secret == "" {
		c.JWT.Secret = "default-jwt-secret-change-in-production"
	}
	if c.JWT.ExpireHours == 0 {
		c.JWT.ExpireHours = 24 * 7 // 7 days
	}

	// Game Service defaults
	if c.GameService.BaseURL == "" {
		c.GameService.BaseURL = "http://localhost:8081"
	}
}

// GetAddress returns the server address
func (c *Config) GetAddress() string {
	return c.Server.Host + ":" + strconv.Itoa(c.Server.Port)
}

// GetExpireDuration returns the JWT expiration as a duration
func (c *Config) GetExpireDuration() time.Duration {
	return time.Duration(c.JWT.ExpireHours) * time.Hour
}
