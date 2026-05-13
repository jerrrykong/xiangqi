package repository

import (
	"context"

	"gorm.io/gorm"

	"github.com/jerrykong/xiangqi/internal/model"
)

// ModelRepository handles AI model data access
type ModelRepository struct {
	db *gorm.DB
}

// NewModelRepository creates a new ModelRepository
func NewModelRepository(db *gorm.DB) *ModelRepository {
	return &ModelRepository{db: db}
}

// Create creates a new model version
func (r *ModelRepository) Create(ctx context.Context, model *model.ModelVersion) error {
	return r.db.WithContext(ctx).Create(model).Error
}

// GetByID retrieves a model version by ID
func (r *ModelRepository) GetByID(ctx context.Context, id int64) (*model.ModelVersion, error) {
	var m model.ModelVersion
	err := r.db.WithContext(ctx).First(&m, id).Error
	if err != nil {
		return nil, err
	}
	return &m, nil
}

// GetByVersion retrieves a model version by version string
func (r *ModelRepository) GetByVersion(ctx context.Context, version string) (*model.ModelVersion, error) {
	var m model.ModelVersion
	err := r.db.WithContext(ctx).Where("version = ?", version).First(&m).Error
	if err != nil {
		return nil, err
	}
	return &m, nil
}

// Update updates a model version
func (r *ModelRepository) Update(ctx context.Context, m *model.ModelVersion) error {
	return r.db.WithContext(ctx).Save(m).Error
}

// UpdateStatus updates the status of a model
func (r *ModelRepository) UpdateStatus(ctx context.Context, id int64, status model.ModelStatus) error {
	return r.db.WithContext(ctx).Model(&model.ModelVersion{}).Where("id = ?", id).Update("status", status).Error
}

// List lists all model versions
func (r *ModelRepository) List(ctx context.Context) ([]model.ModelVersion, error) {
	var models []model.ModelVersion
	err := r.db.WithContext(ctx).Order("created_at DESC").Find(&models).Error
	return models, err
}

// GetLatestOnline gets the latest online model
func (r *ModelRepository) GetLatestOnline(ctx context.Context) (*model.ModelVersion, error) {
	var m model.ModelVersion
	err := r.db.WithContext(ctx).Where("status = ?", model.ModelStatusOnline).
		Order("created_at DESC").First(&m).Error
	if err != nil {
		return nil, err
	}
	return &m, nil
}

// GetOnlineModels gets all online models
func (r *ModelRepository) GetOnlineModels(ctx context.Context) ([]model.ModelVersion, error) {
	var models []model.ModelVersion
	err := r.db.WithContext(ctx).Where("status = ?", model.ModelStatusOnline).
		Order("elo_score DESC").Find(&models).Error
	return models, err
}
