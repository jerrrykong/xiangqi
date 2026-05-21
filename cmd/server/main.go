// Package main is the entry point for the web service
package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/jerrykong/xiangqi/config"
	"github.com/jerrykong/xiangqi/internal/handler"
	"github.com/jerrykong/xiangqi/internal/middleware"
	"github.com/jerrykong/xiangqi/internal/model"
	"github.com/jerrykong/xiangqi/internal/pkg/jwt"
	"github.com/jerrykong/xiangqi/internal/repository"
	"github.com/jerrykong/xiangqi/internal/service"
)

func main() {
	// Initialize log file
	logFile, err := initLog()
	if err != nil {
		log.Fatalf("Failed to initialize log file: %v", err)
	}
	defer logFile.Close()

	// Load configuration
	cfg, err := config.Load("config.yaml")
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Initialize database
	db, err := initDB(cfg, logFile)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// Initialize Redis
	redisClient, err := initRedis(cfg)
	if err != nil {
		log.Printf("Warning: Failed to connect to Redis: %v", err)
		redisClient = nil
	}

	// Initialize repositories
	userRepo := repository.NewUserRepository(db)
	roomRepo := repository.NewRoomRepository(db)
	eloRepo := repository.NewEloRepository(db)
	gameRepo := repository.NewGameRepository(db)
	modelRepo := repository.NewModelRepository(db)

	// Initialize JWT manager
	jwtManager := jwt.NewJWTManager(cfg.JWT.Secret, cfg.JWT.ExpireHours)

	// Initialize services
	gameProxy := service.NewGameProxy(cfg.GameService.BaseURL, cfg.Internal.Secret, fmt.Sprintf("http://%s/internal/game/result", cfg.GetAddress()), redisClient)

	userSvc := service.NewUserService(userRepo, eloRepo, gameRepo, jwtManager)
	eloSvc := service.NewEloService(eloRepo, gameRepo)
	roomSvc := service.NewRoomService(roomRepo, userRepo, eloRepo, gameProxy, redisClient)
	matchSvc := service.NewMatchService(redisClient, roomSvc, gameProxy, eloSvc, userRepo, eloRepo)
	adminSvc := service.NewAdminService(userRepo, roomRepo, gameRepo, eloRepo, modelRepo, matchSvc, redisClient)

	// Initialize handlers
	authHandler := handler.NewAuthHandler(userSvc)
	userHandler := handler.NewUserHandler(userSvc)
	roomHandler := handler.NewRoomHandler(roomSvc)
	matchHandler := handler.NewMatchHandler(matchSvc, roomSvc)
	adminHandler := handler.NewAdminHandler(adminSvc)
	internalHandler := handler.NewInternalHandler(roomSvc, eloSvc)

	// Setup Gin router
	router := setupRouter(cfg, redisClient, jwtManager, authHandler, userHandler, roomHandler, matchHandler, adminHandler, internalHandler)

	// Start match loop
	if redisClient != nil {
		matchSvc.StartMatchLoop()
	}

	// Start room timeout checker
	ctx := context.Background()
	if err := roomSvc.StartTimeoutChecker(ctx); err != nil {
		log.Printf("Warning: Failed to start room timeout checker: %v", err)
	}

	// Create HTTP server
	server := &http.Server{
		Addr:    cfg.GetAddress(),
		Handler: router,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Starting server on %s", cfg.GetAddress())
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Stop match loop
	matchSvc.StopMatchLoop()

	// Stop room timeout checker
	roomSvc.StopTimeoutChecker()

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
}

// initDB initializes the database connection
func initDB(cfg *config.Config, logFile *os.File) (*gorm.DB, error) {
	dsn := fmt.Sprintf(
		"host=%s user=%s password=%s dbname=%s port=%d sslmode=disable TimeZone=UTC",
		cfg.Database.Host,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.DBName,
		cfg.Database.Port,
	)

	gormLogger := logger.New(
		log.New(logFile, "\r\n", log.LstdFlags),
		logger.Config{
			SlowThreshold:             200 * time.Millisecond,
			LogLevel:                  logger.Info,
			IgnoreRecordNotFoundError: true,
			Colorful:                  false,
		},
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: gormLogger,
	})
	if err != nil {
		return nil, err
	}

	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}

	sqlDB.SetMaxOpenConns(cfg.Database.MaxOpenConns)
	sqlDB.SetMaxIdleConns(cfg.Database.MaxIdleConns)
	sqlDB.SetConnMaxLifetime(time.Hour)

	// Auto migrate models - use Migrator().CreateTable to handle existing tables gracefully
	migrator := db.Migrator()
	models := []interface{}{
		&model.User{},
		&model.EloRating{},
		&model.EloHistory{},
		&model.Room{},
		&model.GameHistory{},
		&model.ModelVersion{},
	}
	for _, m := range models {
		if !migrator.HasTable(m) {
			if err := migrator.CreateTable(m); err != nil {
				log.Printf("Warning: failed to create table for %T: %v", m, err)
			}
		}
	}

	return db, nil
}

// initLog initializes the log file
func initLog() (*os.File, error) {
	// Create logs directory if not exists
	logDir := "logs"
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create log directory: %w", err)
	}

	// Generate log filename with date
	logFileName := filepath.Join(logDir, fmt.Sprintf("server_%s.log", time.Now().Format("2006-01-02")))

	// Open log file (append mode)
	logFile, err := os.OpenFile(logFileName, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return nil, fmt.Errorf("failed to open log file: %w", err)
	}

	// Configure standard logger to write to file
	log.SetOutput(logFile)
	log.SetFlags(log.LstdFlags | log.Lshortfile)

	// Also write to console
	multiWriter := io.MultiWriter(os.Stdout, logFile)
	log.SetOutput(multiWriter)

	log.Printf("Log file initialized: %s", logFileName)

	return logFile, nil
}

// initRedis initializes the Redis connection
func initRedis(cfg *config.Config) (*redis.Client, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.Redis.Host, cfg.Redis.Port),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
		PoolSize: cfg.Redis.PoolSize,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, err
	}

	return client, nil
}

// setupRouter configures the Gin router with all routes
func setupRouter(
	cfg *config.Config,
	redisClient *redis.Client,
	jwtManager *jwt.JWTManager,
	authHandler *handler.AuthHandler,
	userHandler *handler.UserHandler,
	roomHandler *handler.RoomHandler,
	matchHandler *handler.MatchHandler,
	adminHandler *handler.AdminHandler,
	internalHandler *handler.InternalHandler,
) *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()

	// Global middleware
	r.Use(gin.Recovery())
	r.Use(middleware.Logger())
	r.Use(middleware.CORS())

	// API v1 group
	api := r.Group("/api/v1")
	{
		// Health check
		api.GET("/health", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{"status": "ok"})
		})

		// Public auth routes (rate limited)
		auth := api.Group("/auth")
		auth.Use(middleware.RateLimit(redisClient, 10, time.Minute))
		{
			auth.POST("/register", authHandler.Register)
			auth.POST("/login", authHandler.Login)
		}

		// Authenticated routes
		authenticated := api.Group("")
		authenticated.Use(middleware.JWTAuth(jwtManager))
		{
			// Auth
			authenticated.POST("/auth/refresh", authHandler.Refresh)

			// Users
			users := authenticated.Group("/users")
			{
				users.GET("/me", userHandler.GetMe)
				users.PATCH("/me", userHandler.UpdateProfile)
				users.GET("/rankings", userHandler.GetRankings)
				users.GET("/:id", userHandler.GetUser)
				users.GET("/:id/history", userHandler.GetHistory)
			}

			// Rooms
			rooms := authenticated.Group("/rooms")
			{
				rooms.POST("", roomHandler.CreateRoom)
				rooms.GET("", roomHandler.ListRooms)
				rooms.GET("/me", roomHandler.GetMyRoom)
				rooms.GET("/:id", roomHandler.GetRoom)
				rooms.POST("/:id/join", roomHandler.JoinRoom)
				rooms.POST("/:id/ready", roomHandler.PlayerReady)
				rooms.POST("/:id/leave", roomHandler.LeaveRoom)
				rooms.DELETE("/:id", roomHandler.DeleteRoom)
			}

			// Match
			match := authenticated.Group("/match")
			{
				match.POST("/pvp", matchHandler.JoinPvP)
				match.DELETE("/pvp", matchHandler.LeavePvP)
				match.GET("/status", matchHandler.GetStatus)
				match.POST("/pve/:level", matchHandler.JoinPvE)
			}
		}

		// Admin routes
		admin := api.Group("/admin")
		admin.Use(middleware.JWTAuth(jwtManager))
		admin.Use(middleware.AdminOnly())
		{
			admin.GET("/users", adminHandler.ListUsers)
			admin.PATCH("/users/:id/ban", adminHandler.BanUser)
			admin.GET("/stats", adminHandler.GetStats)
			admin.POST("/models/upload", adminHandler.UploadModel)
			admin.PATCH("/models/:id/publish", adminHandler.PublishModel)
			admin.GET("/models", adminHandler.ListModels)
		}
	}

	// Internal routes (for Game service callbacks) - outside /api/v1
	internal := r.Group("/internal")
	internal.Use(middleware.InternalAuth(cfg.Internal.Secret))
	{
		internal.POST("/game/result", internalHandler.HandleGameResult)
	}

	return r
}
