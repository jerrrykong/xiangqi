/**
 * AppToast — 轻量提示通知（替代 ElMessage）
 * 
 * 使用方式：
 *   import { showToast } from '@/components/common/AppToast.vue'
 *   showToast('操作成功', 'success')
 *   showToast('操作失败', 'error')
 *   showToast('提示信息', 'info')
 */
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}>()

const visible = ref(false)

onMounted(() => {
  visible.value = true
  setTimeout(() => {
    visible.value = false
  }, props.duration || 2500)
})

const typeIcon: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
}
</script>

<template>
  <Transition name="toast">
    <div v-if="visible" class="app-toast" :class="`toast-${type || 'info'}`">
      <span class="toast-icon">{{ typeIcon[type || 'info'] }}</span>
      <span class="toast-msg">{{ message }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.app-toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  z-index: var(--z-toast);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.toast-success {
  background: rgba(5, 150, 105, 0.92);
  color: #fff;
}
.toast-error {
  background: rgba(220, 38, 38, 0.92);
  color: #fff;
}
.toast-warning {
  background: rgba(217, 119, 6, 0.92);
  color: #fff;
}
.toast-info {
  background: rgba(37, 99, 235, 0.88);
  color: #fff;
}

.toast-icon {
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
}

.toast-msg {
  white-space: nowrap;
}

.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.25s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-16px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-12px);
}
</style>
