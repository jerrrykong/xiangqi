// API 类型定义 — 保留前端通用类型
// HTTP API 相关类型已移除，改为 WS 协议类型 (见 @/ws/types)

// AI 难度
export type Difficulty = 1 | 2 | 3 | 4 | 5

export const DifficultyLabels: Record<Difficulty, string> = {
  1: '简单',
  2: '中等',
  3: '困难',
  4: '大师',
  5: '宗师',
}
