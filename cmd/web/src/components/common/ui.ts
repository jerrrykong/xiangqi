/**
 * UI 工具 — 编程式调用 Toast 和 Confirm
 * 替代 Element Plus 的 ElMessage / ElMessageBox
 */
import { createApp, h } from 'vue'
import AppToast from './AppToast.vue'
import AppConfirm from './AppConfirm.vue'

/** Toast 容器 */
let toastContainer: HTMLDivElement | null = null
function getToastContainer(): HTMLDivElement {
  if (!toastContainer) {
    toastContainer = document.createElement('div')
    toastContainer.id = 'app-toast-container'
    toastContainer.style.cssText = 'position:fixed;top:0;left:0;right:0;pointer-events:none;z-index:9999;display:flex;flex-direction:column;align-items:center;gap:8px;padding-top:24px;'
    document.body.appendChild(toastContainer)
  }
  return toastContainer
}

/**
 * 显示 Toast 通知
 * @param message 消息内容
 * @param type 类型：success | error | warning | info
 * @param duration 显示时长(ms)
 */
export function showToast(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info', duration = 2500): void {
  const container = getToastContainer()
  const wrapper = document.createElement('div')
  container.appendChild(wrapper)

  const app = createApp({
    render() {
      return h(AppToast, { message, type, duration })
    },
  })
  app.mount(wrapper)

  // 自动清理
  setTimeout(() => {
    app.unmount()
    wrapper.remove()
  }, duration + 500)
}

/**
 * 显示确认对话框（Promise 化）
 * @param message 消息内容
 * @param title 标题
 * @param options 选项
 * @returns Promise<boolean> true=确认, false=取消
 */
export function showConfirm(
  message: string,
  title = '提示',
  options?: {
    confirmText?: string
    cancelText?: string
    type?: 'warning' | 'danger' | 'info'
  },
): Promise<boolean> {
  return new Promise((resolve) => {
    const wrapper = document.createElement('div')
    document.body.appendChild(wrapper)

    const app = createApp({
      render() {
        return h(AppConfirm, {
          message,
          title,
          confirmText: options?.confirmText,
          cancelText: options?.cancelText,
          type: options?.type,
          onConfirm: () => {
            resolve(true)
            cleanup()
          },
          onCancel: () => {
            resolve(false)
            cleanup()
          },
        })
      },
    })
    app.mount(wrapper)

    function cleanup() {
      setTimeout(() => {
        app.unmount()
        wrapper.remove()
      }, 300)
    }
  })
}
