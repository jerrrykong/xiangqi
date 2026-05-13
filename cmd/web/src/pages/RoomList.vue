<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useRoomStore } from '@/stores/room'
import type { RoomListItem } from '@/types/api'

const router = useRouter()
const roomStore = useRoomStore()

const currentPage = ref(1)
const pageSize = ref(20)

// 定时刷新
let refreshInterval: number | null = null

onMounted(() => {
  fetchRooms()
  // 每 5 秒刷新一次
  refreshInterval = window.setInterval(fetchRooms, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

async function fetchRooms() {
  try {
    await roomStore.fetchRoomList(currentPage.value, pageSize.value)
  } catch (error) {
    console.error('Failed to fetch rooms:', error)
  }
}

async function handleJoinRoom(room: RoomListItem) {
  try {
    await roomStore.joinRoom(room.room_id)
    ElMessage.success('加入房间成功')
    router.push(`/room/${room.room_id}`)
  } catch (error: any) {
    const message = error.response?.data?.message || '加入房间失败'
    ElMessage.error(message)
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchRooms()
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="room-list-page">
    <!-- 顶部导航 -->
    <header class="room-header">
      <div class="header-content">
        <div class="header-left">
          <h1>房间列表</h1>
        </div>
        <div class="header-right">
          <el-button type="primary" @click="router.push('/lobby')">返回大厅</el-button>
        </div>
      </div>
    </header>

    <main class="room-main">
      <div class="main-content">
        <div class="room-card card">
          <!-- 房间列表 -->
          <div class="room-list">
            <div
              v-for="room in roomStore.roomList"
              :key="room.room_id"
              class="room-item"
              @click="handleJoinRoom(room)"
            >
              <div class="room-item-left">
                <div class="room-icon">
                  <span>🎮</span>
                </div>
                <div class="room-info">
                  <div class="room-name">房间 {{ room.room_id.slice(0, 8) }}</div>
                  <div class="room-meta">
                    房主: {{ room.username }} · {{ formatTime(room.created_at) }}
                  </div>
                </div>
              </div>
              <div class="room-item-right">
                <el-tag type="success" size="large">等待加入</el-tag>
                <el-button type="primary" size="default">加入</el-button>
              </div>
            </div>

            <div v-if="roomStore.roomList.length === 0 && !roomStore.isLoading" class="empty-state">
              <div class="empty-icon">🎯</div>
              <div class="empty-text">暂无等待中的房间</div>
              <el-button type="primary" class="empty-button" @click="router.push('/lobby')">
                创建房间
              </el-button>
            </div>
          </div>

          <!-- 分页 -->
          <div v-if="roomStore.totalRooms > pageSize" class="pagination-wrapper">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="roomStore.totalRooms"
              layout="prev, pager, next"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.room-list-page {
  min-height: 100vh;
  background: linear-gradient(135deg, var(--color-wood-100) 0%, var(--color-wood-200) 100%);
}

.room-header {
  background: var(--color-wood-600);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content h1 {
  font-size: 1.5rem;
  font-weight: bold;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.room-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px;
}

.main-content {
  width: 100%;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(139, 90, 43, 0.15);
  padding: 24px;
}

.room-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.room-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.room-item:hover {
  border-color: var(--color-wood-400);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.room-item-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.room-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-wood-100);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.room-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.room-name {
  font-weight: 500;
  font-size: 1rem;
}

.room-meta {
  font-size: 0.875rem;
  color: #6b7280;
}

.room-item-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.empty-state {
  text-align: center;
  padding: 48px 0;
}

.empty-icon {
  font-size: 3.75rem;
  margin-bottom: 16px;
}

.empty-text {
  color: #6b7280;
  font-size: 1.125rem;
  margin-bottom: 16px;
}

.empty-button {
  margin-top: 16px;
}

.pagination-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}
</style>
