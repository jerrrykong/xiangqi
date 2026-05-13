package model

import "time"

// ModelVersion represents an AI model version
type ModelVersion struct {
	ID        int64       `json:"id" gorm:"primaryKey;autoIncrement"`
	Version   string      `json:"version" gorm:"type:varchar(32);uniqueIndex;not null"`
	ModelPath string      `json:"model_path" gorm:"type:varchar(255);not null"`
	EloScore  *int        `json:"elo_score,omitempty" gorm:"type:int"`
	Status    ModelStatus `json:"status" gorm:"type:varchar(16);not null;default:'training'"`
	Note      string      `json:"note,omitempty" gorm:"type:text"`
	CreatedAt time.Time   `json:"created_at" gorm:"autoCreateTime"`
}

// TableName returns the table name for ModelVersion
func (ModelVersion) TableName() string {
	return "model_versions"
}

// ModelStatus represents the status of a model version
type ModelStatus string

const (
	ModelStatusTraining   ModelStatus = "training"
	ModelStatusValidating ModelStatus = "validating"
	ModelStatusOnline    ModelStatus = "online"
	ModelStatusArchived  ModelStatus = "archived"
)
