# Go 模块定义
module github.com/jerrykong/xiangqi

go 1.21

# Web 服务依赖
require (
	github.com/gin-gonic/gin v1.9.1
	github.com/golang-jwt/jwt/v5 v5.2.0
	gorm.io/gorm v1.25.5
	gorm.io/driver/postgres v1.5.4
	github.com/redis/go-redis/v9 v9.3.0
	github.com/gorilla/websocket v1.5.1
	github.com/joho/godotenv v1.5.1
	golang.org/x/crypto v0.17.0
)

# 开发依赖
require (
	github.com/stretchr/testify v1.8.4
	github.com/DATA-DOG/go-sqlmock v1.5.2
	github.com/valyala/fasthttp v1.50.0
)
