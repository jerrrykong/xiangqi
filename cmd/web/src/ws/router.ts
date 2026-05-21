// WS 消息路由器 — 将服务端推送消息分发到对应的处理函数

type MessageHandler = (data: any) => void

class MessageRouter {
  private handlers = new Map<string, MessageHandler[]>()

  // 注册处理器
  on(type: string, handler: MessageHandler): void {
    const existing = this.handlers.get(type) || []
    existing.push(handler)
    this.handlers.set(type, existing)
  }

  // 移除处理器
  off(type: string, handler: MessageHandler): void {
    const existing = this.handlers.get(type)
    if (existing) {
      this.handlers.set(type, existing.filter(h => h !== handler))
    }
  }

  // 路由消息
  route(type: string, data: any): void {
    const handlers = this.handlers.get(type)
    if (handlers) {
      handlers.forEach(h => {
        try {
          h(data)
        } catch (err) {
          console.error(`[WS Router] Error in handler for "${type}":`, err)
        }
      })
    } else {
      console.warn(`[WS Router] Unhandled message type: ${type}`)
    }
  }

  // 清除所有处理器
  clear(): void {
    this.handlers.clear()
  }
}

export const messageRouter = new MessageRouter()
