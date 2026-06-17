/**
 * AppConfirm — 确认对话框（替代 ElMessageBox.confirm）
 * 
 * 使用方式：
 *   import { showConfirm } from '@/components/common/AppConfirm.vue'
 *   const ok = await showConfirm('确定要退出吗？', '提示')
 */
<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  message: string
  title?: string
  confirmText?: string
  cancelText?: string
  type?: 'warning' | 'danger' | 'info'
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const visible = ref(false)

onMounted(() => {
  visible.value = true
})

function handleConfirm() {
  visible.value = false
  setTimeout(() => emit('confirm'), 250)
}

function handleCancel() {
  visible.value = false
  setTimeout(() => emit('cancel'), 250)
}
</script>

<template>
  <Transition name="confirm">
    <div v-if="visible" class="confirm-overlay" @click.self="handleCancel">
      <div class="confirm-dialog" :class="`confirm-${type || 'info'}`">
        <div class="confirm-header">
          <h3 class="confirm-title">{{ title || '提示' }}</h3>
        </div>
        <div class="confirm-body">
          <p>{{ message }}</p>
        </div>
        <div class="confirm-footer">
          <button class="btn btn-secondary btn--sm" @click="handleCancel">
            {{ cancelText || '取消' }}
          </button>
          <button
            class="btn btn--sm"
            :class="type === 'danger' ? 'btn-danger' : 'btn-primary'"
            @click="handleConfirm"
          >
            {{ confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-bg-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
}

.confirm-dialog {
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  max-width: 400px;
  width: 90%;
  overflow: hidden;
}

.confirm-header {
  padding: var(--space-5) var(--space-6) 0;
}

.confirm-title {
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
  color: var(--color-text-primary);
}

.confirm-body {
  padding: var(--space-4) var(--space-6);
  color: var(--color-text-secondary);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
}

.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--color-wood-light);
}

.confirm-enter-active {
  transition: all 0.25s ease-out;
}
.confirm-leave-active {
  transition: all 0.2s ease-in;
}
.confirm-enter-from {
  opacity: 0;
}
.confirm-enter-from .confirm-dialog {
  transform: scale(0.9) translateY(20px);
}
.confirm-leave-to {
  opacity: 0;
}
.confirm-leave-to .confirm-dialog {
  transform: scale(0.95) translateY(10px);
}
</style>
