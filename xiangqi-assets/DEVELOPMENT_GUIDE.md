# 楚漢爭鋒 — Web 版中国象棋开发指南

> 版本：v1.0.0 | 更新日期：2026-06-13 | 基于 Ardot 设计稿 & demo.html 地面真值

---

## 目录

1. [项目概述](#1-项目概述)
2. [设计系统](#2-设计系统)
3. [界面详细说明](#3-界面详细说明)
   - [3.1 登录界面](#31-登录界面)
   - [3.2 游戏大厅](#32-游戏大厅)
   - [3.3 对局界面](#33-对局界面)
   - [3.4 复盘界面](#34-复盘界面)
   - [3.5 设置界面](#35-设置界面)
   - [3.6 排行榜弹窗](#36-排行榜弹窗)
   - [3.7 历史对局弹窗](#37-历史对局弹窗)
   - [3.8 胜负提示弹窗](#38-胜负提示弹窗--设计预留)
   - [3.9-3.11 移动端界面](#39-311-移动端界面)
4. [UI 元素/组件详解](#4-ui-元素组件详解)
5. [资源文件清单](#5-资源文件清单)
6. [技术架构建议](#6-技术架构建议)
7. [功能逻辑开发指南](#7-功能逻辑开发指南)
8. [响应式与移动端适配](#8-响应式与移动端适配)
9. [附录](#9-附录)

---

## 1. 项目概述

**楚漢爭鋒**是一款 Web 版中国象棋在线对战平台，采用中国传统木质风格设计（扁平设计 + 暖色调中国风），支持 PC 端与移动端。

### 核心特性
- 在线人人对弈（匹配/创建房间）
- 人机对弈（AI 引擎）
- 棋局复盘（播放控制/着法浏览）
- 排行榜 / 历史对局记录
- 账号系统（登录/注册/游客模式）
- 完整的 11 个界面（含 PC + 移动端适配）

### Ardot 设计文件
- **文件 ID**：`692177145468803`
- **链接**：https://ardot.tencent.com/file/692177145468803

---

## 2. 设计系统

### 2.1 色彩体系

#### 主色调（暖色木质风）

| 变量名 | 色值 | 用途 |
|--------|------|------|
| `--color-bg-primary` | `#FFFBEB` | 米黄主背景 |
| `--color-bg-secondary` | `#FFF7D6` | 浅米黄次级背景 |
| `--color-bg-card` | `#FFFFFF` | 卡片背景白 |
| `--color-bg-overlay` | `rgba(0,0,0,0.45)` | 遮罩层 |

#### 强调色（金色系）

| 变量名 | 色值 | 用途 |
|--------|------|------|
| `--color-gold` | `#D97706` | 金色主强调（按钮/边框/进度条） |
| `--color-gold-light` | `#F59E0B` | 金色浅（hover/渐变起点） |
| `--color-gold-dark` | `#B45309` | 金色深（边框/文字 hover） |
| `--color-gold-pressed` | `#92400E` | 金色按压态 |

#### 木质棕色系

| 变量名 | 色值 | 用途 |
|--------|------|------|
| `--color-wood-dark` | `#78350F` | 深胡桃木（标题） |
| `--color-wood` | `#92400E` | 胡桃木（正文） |
| `--color-wood-medium` | `#B45309` | 中胡桃 |
| `--color-wood-light` | `#D97706` | 浅木色（边框） |
| `--color-wood-bg` | `#FDE68A` | 木纹底色 |

#### 文字色

| 变量名 | 色值 | 用途 |
|--------|------|------|
| `--color-text-primary` | `#451A03` | 主文字 |
| `--color-text-secondary` | `#78350F` | 次要文字 |
| `--color-text-tertiary` | `#A16207` | 辅助文字 |
| `--color-text-inverse` | `#FFFBEB` | 反色文字（深色底） |
| `--color-text-muted` | `#D4A574` | 禁用/占位 |

#### 功能色

| 变量名 | 色值 | 用途 |
|--------|------|------|
| `--color-success` | `#059669` | 成功（胜局标签） |
| `--color-error` | `#DC2626` | 错误/红方指示（负局标签/计时警告） |
| `--color-warning` | `#D97706` | 警告（和局标签） |

### 2.2 字体系统

| 变量名 | 字体栈 | 用途 |
|--------|--------|------|
| `--font-serif` | `'Noto Serif TC', 'Source Han Serif SC', 'SimSun', serif` | 标题/按钮/名称 |
| `--font-sans` | `'Noto Sans TC', 'PingFang SC', 'Microsoft YaHei', sans-serif` | 正文全局 |
| `--font-mono` | `'Consolas', 'Source Code Pro', monospace` | 计时器/着法编号/分数 |

### 2.3 字号层级

| 变量 | 大小 | 用途 |
|------|------|------|
| `--text-xs` | `0.75rem` (12px) | 辅助信息/统计标签 |
| `--text-sm` | `0.875rem` (14px) | 次要文字/按钮小号 |
| `--text-base` | `1rem` (16px) | 正文基准 |
| `--text-lg` | `1.125rem` (18px) | 子标题/弹窗标题 |
| `--text-xl` | `1.25rem` (20px) | 玩家名 |
| `--text-2xl` | `1.5rem` (24px) | 计时器 |
| `--text-3xl` | `1.875rem` (30px) | 界面标题 |

### 2.4 间距尺度（4px 基准）

| 变量 | rem | 实际 |
|------|-----|------|
| `--space-1` | 0.25rem | 4px |
| `--space-2` | 0.5rem | 8px |
| `--space-3` | 0.75rem | 12px |
| `--space-4` | 1rem | 16px |
| `--space-5` | 1.25rem | 20px |
| `--space-6` | 1.5rem | 24px |
| `--space-8` | 2rem | 32px |
| `--space-10` | 2.5rem | 40px |
| `--space-12` | 3rem | 48px |

### 2.5 圆角

| 变量 | 值 | 用途 |
|------|-----|------|
| `--radius-xs` | 4px | 小标签/速度按钮 |
| `--radius-sm` | 6px | 文字按钮 hover |
| `--radius-md` | 8px | 按钮/输入框 |
| `--radius-lg` | 12px | 卡片 |
| `--radius-xl` | 16px | 大厅玩家卡/弹窗 |
| `--radius-2xl` | 24px | 登录卡 |
| `--radius-full` | 9999px | 圆形头像/开关 |

### 2.6 阴影

| 变量 | 值 |
|------|-----|
| `--shadow-sm` | `0 1px 3px rgba(120,53,15,0.12)` |
| `--shadow-md` | `0 4px 12px rgba(120,53,15,0.15)` |
| `--shadow-lg` | `0 8px 24px rgba(120,53,15,0.2)` |
| `--shadow-xl` | `0 12px 40px rgba(120,53,15,0.25)` |
| `--shadow-inner` | `inset 0 2px 4px rgba(120,53,15,0.1)` |

### 2.7 棋盘参数常量

| 参数 | 值 | 说明 |
|------|-----|------|
| 棋盘原生宽度 `--board-w` | 540px | board.svg 原始宽 |
| 棋盘原生高度 `--board-h` | 600px | board.svg 原始高 |
| 格距 `--cell` | 60px | 列宽/行高 |
| 边距 `--pad` | 30px | 棋盘内边距 |
| 棋子尺寸 `--piece-size` | 48px | 棋子原生边长 |
| 偏移 `POFF_N` | 24px | 棋子中心偏移（piece-size / 2） |

---

## 3. 界面详细说明

### 3.1 登录界面

**设计尺寸**：500×900（Ardot 画布）

#### 业务功能
- 用户名 + 密码登录
- 注册入口
- 游客模式（免登录进入）
- 版本号展示

#### 布局结构

```
┌─────────────────────────────┐
│      login-page (flex居中)   │
│  ┌─────────────────────────┐ │
│  │     login-card          │ │
│  │  max-width: 420px       │ │
│  │  ┌───────────────────┐  │ │
│  │  │  game-title-img   │  │ │  ← 文字 Logo SVG (280×75)
│  │  │  (横向文字Logo)    │  │ │
│  │  └───────────────────┘  │ │
│  │  game-subtitle          │ │  ← "中国象棋在线对战平台"
│  │  ┌───────────────────┐  │ │
│  │  │  login-form       │  │ │
│  │  │  [用户名 input]    │  │ │  ← .form-input
│  │  │  [密码 input]      │  │ │  ← .form-input type=password
│  │  └───────────────────┘  │ │
│  │  login-actions          │ │
│  │  [登 录] 主按钮         │ │  ← .btn-primary .btn--block .btn--lg
│  │  [注 册] 次要按钮       │ │  ← .btn-secondary .btn--block
│  │  login-guest            │ │
│  │  [游客模式] 文字按钮    │ │  ← .btn-text
│  │  login-footer           │ │  ← v1.0.0 · 楚漢爭鋒工作室
│  └─────────────────────────┘ │
└─────────────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.login-page` | 全屏居中容器，渐变背景 |
| `.login-card` | 白色卡片，金色双线边框，圆角 24px |
| `.game-title-img` | 文字 Logo 图片，280×75 |
| `.game-subtitle` | 副标题，衬线字体，字间距 .2em |
| `.login-form` | flex column，表单输入区 |
| `.login-actions` | 登录/注册按钮区 |
| `.login-guest` | 游客模式入口 |
| `.login-footer` | 底部版本信息 |

#### 交互逻辑
- 输入用户名/密码 → 点击「登录」→ 验证 → 跳转大厅
- 点击「注册」→ 跳转注册页（或弹出注册表单）
- 点击「游客模式」→ 直接进入大厅（有限功能）
- Demo 中登录按钮直接跳转 `currentTab='lobby'`

### 3.2 游戏大厅

**设计尺寸**：940×900（PC 端）

#### 业务功能
- 玩家信息展示（头像/昵称/段位/战绩统计）
- 新对局（创建房间/匹配）
- 加入对局（输入房间号）
- 人机对弈
- 棋局复盘入口
- 系统设置入口
- 排行榜 / 历史记录入口

#### 布局结构

```
┌──────────────────────────────────────────┐
│              lobby-page                   │
│  max-width: 1440px, margin: 0 auto       │
│  ┌──────────────────────────────────────┐ │
│  │  lobby-header                        │ │
│  │  [brand-name-img] [🏆排行榜 📋历史 ⚙设置] │ │
│  └──────────────────────────────────────┘ │
│  ┌──────────────────────────────────────┐ │
│  │  lobby-player-card                   │ │
│  │  [👤 avatar] 张三丰                   │ │
│  │             业余九段                  │ │
│  │             [256胜 | 48负 | 12和 | 84.2%]│ │
│  └──────────────────────────────────────┘ │
│  ┌──────────────────────────────────────┐ │
│  │  lobby-actions (单列居中)             │ │
│  │  ┌──────────────────────────────┐    │ │
│  │  │ ⚔ 新对局                     │    │ │  ← .lobby-action-btn
│  │  ├──────────────────────────────┤    │ │
│  │  │ 🔗 加入对局                   │    │ │
│  │  ├──────────────────────────────┤    │ │
│  │  │ 🤖 人机对弈                   │    │ │
│  │  ├──────────────────────────────┤    │ │
│  │  │ 📖 棋局复盘                   │    │ │
│  │  ├──────────────────────────────┤    │ │
│  │  │ ⚙ 系统设置                   │    │ │
│  │  └──────────────────────────────┘    │ │
│  └──────────────────────────────────────┘ │
│  ┌──────────────────────────────────────┐ │
│  │  lobby-links                         │ │
│  │     🏆 排行榜    📋 历史记录         │ │
│  └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.lobby-page` | 最大宽度 1440px 居中 |
| `.lobby-header` | flex space-between 顶栏 |
| `.lobby-player-card` | 玩家信息卡，金色边框，flex 布局 |
| `.lobby-actions` | 操作按钮区，flex column |
| `.lobby-action-btn` | 单个操作按钮，max-width:360px，白底+木色边框，hover 金色边框 |
| `.btn-icon-w` | 按钮前的 emoji/图标，28px |
| `.btn-label` | 按钮文字，衬线字体 |
| `.lobby-links` | 底部快捷链接 |
| `.lobby-link-item` | 单个链接项 |
| `.avatar` | 64px 圆形头像容器 |

#### 交互逻辑
- 点击「新对局」→ 进入匹配或创建房间 → 跳转对局页
- 点击「加入对局」→ 弹出输入房间号对话框
- 点击「人机对弈」→ 选择难度 → 进入 AI 对局
- 点击「棋局复盘」→ 跳转复盘页
- 点击「排行榜/历史记录」→ 弹出全屏 overlay 弹窗

### 3.3 对局界面

**设计尺寸**：1440×900（PC 端）

#### 业务功能
- 实时棋盘展示（含 32 枚棋子）
- 红黑双方玩家信息 + 倒计时
- 当前轮次指示
- 走棋交互（点击选中/移动棋子）
- 着法记录（侧边栏/移动端底部面板）
- 操作按钮：求和/认输/悔棋/退出
- 房间号展示

#### 布局结构（PC 端）

```
┌─────────────────────────────────────────────────────┐
│  game-topbar                                         │
│  [text-logo 180×48]    [房间#8842 | 回合23 | ●红方走棋]│
├───────────────────────┬─────────────────────────────┤
│  game-center          │  game-sidebar (280px)        │
│  ┌──────────────────┐ │  ┌─────────────────────────┐ │
│  │ game-opponent    │ │  │ sidebar-header           │ │
│  │ [李]李四海 业余八段│ │  │ 着法记录          23手  │ │
│  │          08:45   │ │  ├─────────────────────────┤ │
│  ├──────────────────┤ │  │ move-list (overflow-y)   │ │
│  │ game-board-area  │ │  │ 1. 炮二平五  马8进7      │ │
│  │ ┌──────────────┐ │ │  │ 2. 马二进三  车9平8      │ │
│  │ │ board-frame  │ │ │  │ ...                      │ │
│  │ │ (JS动态缩放)  │ │ │  └─────────────────────────┘ │
│  │ └──────────────┘ │ │                             │
│  ├──────────────────┤ │                             │
│  │game-actions-inline│ │                             │
│  │[求和][认输][悔棋][退出]│                            │
│  ├──────────────────┤ │                             │
│  │ game-player      │ │                             │
│  │ [张]张三丰 业余九段│ │                             │
│  │          13:58   │ │                             │
│  └──────────────────┘ │                             │
└───────────────────────┴─────────────────────────────┘
```

#### 布局结构（移动端）

```
┌─────────────────────┐
│  game-topbar (紧凑)  │
│ [logo 130×35] [房间/回合] │
├─────────────────────┤
│  game-opponent      │
│  [李] 李四海  08:45 │
├─────────────────────┤
│  game-board-area    │
│  (自适应缩放)        │
├─────────────────────┤
│  game-actions-inline │
│  [求和][认输][悔棋][退出]│
├─────────────────────┤
│  game-player        │
│  [张] 张三丰  13:58 │
├─────────────────────┤
│  mobile-toggle-bar  │
│  [📜 着法记录]       │  ← 点击弹出 bottom sheet
└─────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.game-page` | 全高 flex column，隐藏溢出 |
| `.game-topbar` | 顶部信息栏 |
| `.turn-indicator` / `.turn-red` / `.turn-black` | 轮次指示器（圆形色点 + 文字） |
| `.game-main` | 主体 flex row（移动端 column） |
| `.game-center` | 中央区域（对手+棋盘+操作+我方） |
| `.game-opponent` / `.game-player` | 双方信息条 |
| `.ava` | 对局头像 44px 圆形 |
| `.opp-info` / `.opp-name` / `.opp-level` | 玩家名称段位 |
| `.opp-timer` / `.opp-timer--warn` | 倒计时器（<30s 闪烁警告） |
| `.game-board-area` | 棋盘容器（flex 居中） |
| `.board-frame` | 棋盘框架（relative，JS 设置宽高） |
| `.board-bg` | 棋盘背景图（absolute 铺满） |
| `.piece-el` / `.piece-el.sel` | 棋子（absolute 定位，选中态金色光晕动画） |
| `.game-actions-inline` | 底部操作按钮行 |
| `.game-sidebar` | 桌面端着法侧边栏 280px |
| `.move-list` / `.move-item` / `.move-num` / `.move-red` / `.move-black` | 着法记录 |
| `.mobile-toggle-bar` / `.mobile-toggle-btn` | 移动端底部切换栏（默认隐藏） |
| `.mobile-panel-overlay` / `.mobile-panel-sheet` | 移动端底部可折叠面板 |

#### 关键 JS 逻辑（棋盘自适应缩放）

```javascript
// 原生参数
const NATIVE_W = 540, NATIVE_H = 600
const CELL_N = 60, PAD_N = 30, PSIZE_N = 48, POFF_N = 24
const MIN_W = 300, MIN_H = 333

// 计算缩放
const calcBoardScale = (area, scaleRef, dispW, dispH) => {
  const availW = area.clientWidth - 48   // 24px padding × 2
  const availH = area.clientHeight - 48
  let sw = availW / NATIVE_W
  let sh = availH / NATIVE_H
  let s = Math.min(sw, sh)
  s = Math.min(s, 1)                    // 不放大超过原生
  if (NATIVE_W * s < MIN_W) s = MIN_W / NATIVE_W
  if (NATIVE_H * s < MIN_H) s = Math.max(s, MIN_H / NATIVE_H)
  scaleRef.value = s
  dispW.value = Math.round(NATIVE_W * s)
  dispH.value = Math.round(NATIVE_H * s)
}

// 棋子坐标计算（computed）
const pieces = computed(() => {
  const s = boardScale.value
  const cell = CELL_N * s, pad = PAD_N * s
  const poff = POFF_N * s, psize = Math.round(PSIZE_N * s)
  return rawPieces.map(p => ({
    x: Math.round(pad + p.col * cell - poff),
    y: Math.round(pad + p.row * cell - poff),
    ds: psize, ...
  }))
})

// ResizeObserver 监听棋盘区域
watch(currentTab, (tab) => {
  nextTick(() => {
    if (tab === 'game' && boardArea.value) {
      updateBoardScale()
      gameRO = new ResizeObserver(() => updateBoardScale())
      gameRO.observe(boardArea.value)
    }
  })
})
```

#### 棋子数据格式（Demo 中 cols 0-8, rows 0-9）

```javascript
// 黑方 row 0-3, 红方 row 6-9
// row 4-5 为河界
const rawPieces = [
  { id:'br0', col:0, row:0, svg:'black-ju.svg',    label:'車', side:'black' },
  { id:'rr4', col:4, row:9, svg:'red-shuai.svg',   label:'帥', side:'red'  },
  // ... 共 32 枚
]
```

### 3.4 复盘界面

**设计尺寸**：1440×900（PC 端）

#### 业务功能
- 棋局回放（一步步播放）
- 播放控制：上一步/播放暂停/下一步
- 进度条（可拖拽跳转）
- 播放速度切换（0.5x / 1x / 2x）
- 着法记录查看（弹出面板）
- 对局信息查看（弹出面板）
- 导入棋谱（.pgn 等格式）

#### 布局结构

```
┌────────────────────────────────────────────┐
│  review-header                              │
│  [← 返回] 棋局复盘          [📥 导入棋谱]   │
├────────────────────────────────────────────┤
│  review-main                                │
│  ┌────────────────────────────────────────┐ │
│  │  review-board-area                     │ │
│  │  ┌──────────────────────┐              │ │
│  │  │  board-frame (缩放)   │              │ │
│  │  └──────────────────────┘              │ │
│  │  ┌──────────────────────────────────┐  │ │
│  │  │  playback-controls               │  │ │
│  │  │  [⏮] [▶/⏸] [⏭] [━━━━━━━] [速度] │  │ │
│  │  │                  10 / 47         │  │ │
│  │  └──────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────┐  │ │
│  │  │  review-toggle-bar               │  │ │
│  │  │  [📜 着法记录] [📊 对局信息]     │  │ │
│  │  └──────────────────────────────────┘  │ │
│  └────────────────────────────────────────┘ │
└────────────────────────────────────────────┘

弹出面板（点击 toggle-bar 触发）:
┌──────────────────────┐
│  review-overlay       │  ← 半透明遮罩
│  ┌──────────────────┐ │
│  │  review-popup    │ │  ← 居中弹出卡
│  │  [着法记录  ✕]   │ │     max-width:520px
│  │  ┌──────────────┐ │ │
│  │  │ move-list    │ │ │
│  │  └──────────────┘ │ │
│  └──────────────────┘ │
└──────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.review-page` | 全高 flex column |
| `.review-header` | 顶部栏 |
| `.review-main` | 主体 |
| `.review-board-area` | 棋盘区域 flex column |
| `.playback-controls` | 播放控制栏 |
| `.pb-btn` / `.pb-btn--play` | 播放控制按钮（圆形，播放按钮更大更金） |
| `.progress-bar` / `.progress-fill` | 进度条（6px 高，金色填充） |
| `.progress-label` | 进度数字标签 |
| `.speed-options` / `.speed-btn` | 速度选择按钮组 |
| `.review-toggle-bar` / `.toggle-item` | 切换按钮行（着法/信息） |
| `.review-overlay` | 弹出遮罩（点击空白关闭） |
| `.review-popup` | 弹出卡 |
| `.game-info-card` | 对局信息卡（桌面端隐藏，仅在弹出面板内用） |

#### 关键 JS 逻辑

```javascript
const reviewStep = ref(10)       // 当前步
const reviewTotal = 47           // 总手数

// 进度条点击跳转
const seekReview = (e) => {
  const rect = e.currentTarget.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  reviewStep.value = Math.round(pct * reviewTotal)
}

// 复盘弹出面板切换
const reviewPopup = ref('')  // '' | 'moves' | 'info'
```

### 3.5 设置界面

**设计尺寸**：720×900

#### 业务功能
- 对局设置（音效/棋盘主题/走棋确认）
- 账号设置（昵称/修改密码）
- 关于信息（版本/开发者）
- 退出登录

#### 布局结构

```
┌───────────────────────────┐
│  settings-page            │
│  max-width: 640px         │
│  ┌───────────────────────┐ │
│  │ settings-header       │ │
│  │ [← 返回] 系统设置      │ │
│  ├───────────────────────┤ │
│  │ 对局设置              │ │
│  │ ┌───────────────────┐ │ │
│  │ │ settings-group    │ │ │
│  │ │ 音效          开启│ │ │
│  │ │ 棋盘主题  传统木质│ │ │
│  │ │ 走棋确认      关闭│ │ │
│  │ └───────────────────┘ │ │
│  ├───────────────────────┤ │
│  │ 账号                  │ │
│  │ ┌───────────────────┐ │ │
│  │ │ 昵称        张三丰│ │ │
│  │ │ 修改密码        › │ │ │
│  │ └───────────────────┘ │ │
│  ├───────────────────────┤ │
│  │ 关于                  │ │
│  │ ┌───────────────────┐ │ │
│  │ │ 版本       v1.0.0 │ │ │
│  │ │ 开发者 楚漢爭鋒工作室│ │ │
│  │ └───────────────────┘ │ │
│  ├───────────────────────┤ │
│  │    [退出登录]          │ │  ← .btn-danger
│  │  [text-logo]          │ │
│  │  v1.0.0               │ │
│  └───────────────────────┘ │
└───────────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.settings-page` | 最大宽 640px，居中 |
| `.settings-header` | 返回 + 标题 |
| `.settings-section` / `.settings-section-title` | 分组标题 |
| `.settings-group` | 白底分组卡片，圆角 12px |
| `.settings-item` | 单行设置项，flex space-between |
| `.item-label` / `.item-desc` / `.item-value` | 标签/描述/当前值 |
| `.settings-about` | 关于区域，居中，小字 |

### 3.6 排行榜弹窗

**设计尺寸**：480×680（Ardot 画布）  
**实现方式**：Demo 中为全屏 overlay（.lobby-overlay），在大厅页内触发

#### 布局结构

```
┌──────────────────────┐
│  lobby-overlay        │  ← 全屏白色背景
│  ┌──────────────────┐ │
│  │ overlay-header   │ │
│  │ 🏆 排行榜    [✕] │ │
│  ├──────────────────┤ │
│  │ overlay-body     │ │
│  │ (overflow-y)     │ │
│  │ 1 王天元 特级大师 2847分  │
│  │ 2 赵弈秋 特级大师 2793分  │
│  │ 3 孙棋圣 特级大师 2756分  │
│  │ ...              │ │
│  └──────────────────┘ │
└──────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.lobby-overlay` | 全屏白色弹窗容器 |
| `.overlay-header` | 弹窗标题栏 |
| `.overlay-close` | 关闭按钮（X） |
| `.overlay-body` | 可滚动内容区 |
| `.popup-rank-item` | 排行条目 |
| `.popup-rank` | 排名数字（前三金色/银色/铜色） |
| `.popup-rank-name` | 玩家名 |
| `.popup-rank-info` | 段位信息 |
| `.popup-rank-score` | 分数（等宽字体，右对齐） |

#### 数据结构

```javascript
const rankData = [
  { name:'王天元', level:'特级大师', score:2847 },
  // ...
]
```

### 3.7 历史对局弹窗

**设计尺寸**：500×680（Ardot 画布）
**实现方式**：Demo 中为全屏 overlay，在大厅页内触发

#### 布局结构

```
┌──────────────────────┐
│  lobby-overlay        │
│  ┌──────────────────┐ │
│  │ overlay-header   │ │
│  │ 📋 历史对局  [✕] │ │
│  ├──────────────────┤ │
│  │ overlay-body     │ │
│  │ [胜] 李四海  2026-06-11  │
│  │ [负] 王天元  2026-06-10  │
│  │ [和] 赵弈秋  2026-06-09  │
│  │ ...              │ │
│  └──────────────────┘ │
└──────────────────────┘
```

#### 关键 CSS 类名

| 类名 | 作用 |
|------|------|
| `.popup-history-item` | 历史对局条目 |
| `.popup-result` | 结果标签（.win 绿 / .lose 红 / .draw 黄） |

#### 数据结构

```javascript
const historyData = [
  { opponent:'李四海', result:'win',  resultLabel:'胜', date:'2026-06-11 15:30' },
  // ...
]
```

### 3.8 胜负提示弹窗（设计预留）

**设计尺寸**：360×300（Ardot 画布）  
**当前状态**：仅在 Ardot 设计稿中存在，Demo 中**未实现**

#### 建议实现

```html
<!-- 对局结束弹窗 -->
<transition name="overlay">
<div v-if="gameOver" class="review-overlay" @click.self="gameOver=null">
  <div class="review-popup" style="max-width:360px; text-align:center; padding:32px 24px">
    <div style="font-size:48px; margin-bottom:8px">{{ winner === 'red' ? '🏆' : '💪' }}</div>
    <div style="font-family:var(--font-serif); font-size:var(--text-2xl); font-weight:700; color:var(--color-wood-dark); margin-bottom:4px">
      {{ winner === 'red' ? '红方胜' : '黑方胜' }}
    </div>
    <div style="font-size:var(--text-sm); color:var(--color-text-tertiary); margin-bottom:24px">
      着法 47 手 · 用时 14:23
    </div>
    <div style="display:flex; gap:8px; justify-content:center">
      <button class="btn btn-secondary">复盘</button>
      <button class="btn btn-primary">再来一局</button>
    </div>
  </div>
</div>
</transition>
```

### 3.9-3.11 移动端界面

**设计尺寸**：390×844（Ardot 画布中为独立画板）

移动端通过**响应式 CSS**（`@media (max-width: 768px)`）在同一套 HTML 上实现，不需要单独页面。

#### 移动端关键适配点

| 界面 | PC 端 → 移动端变化 |
|------|-------------------|
| **登录** | login-card padding 减小，game-title-img 240×64 |
| **大厅** | lobby-header 纵向排列；lobby-action-btn max-width:100% |
| **对局** | game-main flex-direction:column；game-sidebar 隐藏 → mobile-toggle-bar 显示；棋盘 padding 减少 |
| **复盘** | review-main column；review-overlay → 底部弹出；playback-controls 紧凑 flex-wrap |
| **设置** | settings-page max-width 保持 640px，padding 自适应 |

#### 移动端特有组件

| 组件 | CSS 类名 | 说明 |
|------|---------|------|
| 底部切换栏 | `.mobile-toggle-bar` (默认 `display:none`) | 768px 以下显示 |
| 切换按钮 | `.mobile-toggle-btn` / `.active` | 金色激活态 |
| 底部面板遮罩 | `.mobile-panel-overlay` / `.open` | 半透明遮罩，点击关闭 |
| 底部面板卡片 | `.mobile-panel-sheet` / `.open` | 圆角顶部，transform 动画 |
| 面板拖拽条 | `.mobile-panel-handle` | 36×4 灰色横条 |

---

## 4. UI 元素/组件详解

### 4.1 按钮系统

```css
/* 基础按钮 */
.btn                    /* inline-flex, 居中, 衬线字体, 2px透明边框 */

/* 语义变体 */
.btn-primary            /* 金色渐变背景, 白字, 金色边框 */
.btn-secondary          /* 白色背景, 木色文字, 浅木色边框 */
.btn-danger             /* 红色背景, 白字 */
.btn-text               /* 无背景, 无边框, 木色文字 */

/* 尺寸变体 */
.btn--sm                /* padding小, font-sm */
.btn--lg                /* padding大, font-lg */
.btn--block             /* width:100% */

/* 状态 */
.btn:hover              /* translateY(-1px) + 阴影增强 */
.btn:active             /* translateY(+1px) + 内阴影 */
.btn:disabled           /* opacity:0.5 + not-allowed */
```

### 4.2 大厅操作按钮（大卡片样式）

```css
.lobby-action-btn       /* flex, 白色背景, 浅木色边框, max-width:360px, min-height:52px */
.lobby-action-btn:hover /* 金色边框, 浅黄背景, 抬升2px */
.btn-icon-w             /* emoji/图标, 28px, 不缩放 */
.btn-label              /* 衬线字体, 加粗, 木色 */
```

### 4.3 表单输入框

```css
.form-input             /* 全宽, 白底, 2px浅木色边框, rounded 8px */
.form-input:hover       /* 边框变金 */
.form-input:focus       /* 边框金色 + 金色发光阴影 3px */
.form-input::placeholder/* 浅木色文字 */
```

### 4.4 棋盘 (ChessBoard)

**棋盘 SVG**：`assets/svg/board.svg`（540×600，含木色底 + 格线 + 楚河汉界）

**自适应缩放机制**：
```
可用空间 = 容器 clientWidth/Height - 48px padding
缩放比   = min(可用宽/540, 可用高/600)
          → 不超过 1.0（不放大）
          → 不低于最小尺寸 300×333
棋子坐标 = col×cell + pad - piece_size/2
```

**布局层级**：
```
.board-frame (relative, JS设置宽高, overflow:hidden)
  ├── .board-bg (absolute, 100%铺满)
  └── .piece-el × 32 (absolute, JS计算left/top)
       └── <img> (棋子SVG, drop-shadow)
```

### 4.5 棋子 (ChessPiece)

| 红方 | 黑方 | SVG 文件 |
|------|------|---------|
| 帥 | 將 | `red-shuai.svg` / `black-jiang.svg` |
| 仕 | 士 | `red-shi.svg` / `black-shi.svg` |
| 相 | 象 | `red-xiang.svg` / `black-xiang.svg` |
| 馬 | 馬 | `red-ma.svg` / `black-ma.svg` |
| 車 | 車 | `red-ju.svg` / `black-ju.svg` |
| 炮 | 砲 | `red-pao.svg` / `black-pao.svg` |
| 兵 | 卒 | `red-bing.svg` / `black-zu.svg` |

**棋子状态**：
```css
.piece-el               /* 正常态: drop-shadow 木质阴影 */
.piece-el:hover         /* 悬停: 抬升2px + 阴影加深 */
.piece-el.sel img       /* 选中: 金色光晕 + 呼吸动画 (1.2s alternate) */
```

### 4.6 玩家信息 (PlayerInfo)

**位置**：对局页顶部（对手）和底部（我方）

```html
<div class="game-opponent / game-player">
  <div class="ava">姓</div>        <!-- 44px 圆形头像 (PC) / 32px (移动端) -->
  <div class="opp-info">
    <div class="opp-name">姓名</div>    <!-- 衬线15px, 加粗, 深木色, 溢出省略 -->
    <div class="opp-level">段位</div>   <!-- 12px, 浅棕 -->
  </div>
  <div class="opp-timer">00:00</div>    <!-- 等宽24px, 加粗, 最小85px宽 -->
</div>
```

### 4.7 计时器 (GameTimer)

```css
.opp-timer              /* 等宽字体, 24px, 加粗, 木色, 米黄底, 圆角8px */
.opp-timer--warn        /* <30秒: 红色 + 闪烁动画(0.5s alternate) */
```

**Demo 计时逻辑**：
```javascript
setInterval(() => {
  if (currentTab === 'game') {
    if (turn === 'red') redTime = max(0, redTime - 1)
    else blackTime = max(0, blackTime - 1)
  }
}, 1000)

const fmtTime = (s) => {
  const m = Math.floor(s / 60), sc = s % 60
  return `${String(m).padStart(2,'0')}:${String(sc).padStart(2,'0')}`
}
```

### 4.8 着法记录 (MoveList)

```css
.move-list              /* flex column, overflow-y, padding 8px */
.move-item              /* flex row, padding 6px 12px, 圆角6px, hover浅黄 */
.move-item.active       /* 激活态: 金色半透明背景, 加粗 */
.move-num               /* 等宽11px, 浅棕, 最小24px */
.move-red               /* 红方着法: 朱红色 #C53030 */
.move-black             /* 黑方着法: 深灰 #2D3748 */
```

**数据结构**：
```javascript
const gameMoves = [
  { idx:1, red:'炮二平五', black:'马8进7' },
  { idx:2, red:'马二进三', black:'车9平8' },
  // idx 从 1 开始, black 可能为 null（最后一手）
]
```

### 4.9 播放控制 (PlaybackControls)

```css
.playback-controls      /* flex row, 白底卡片, 圆角12px, 间距16px */
.pb-btn                 /* 40px 圆形按钮, 米黄底 */
.pb-btn--play           /* 48px 圆形按钮, 金色底, 白字（播放/暂停） */
.playback-progress      /* flex:1, flex column */
.progress-bar           /* 100%×6px, 米黄底, 圆角, overflow:hidden, cursor:pointer */
.progress-fill          /* 金色填充, 宽度过渡动画 */
.speed-btn              /* 小圆角按钮, 激活态金色 */
```

### 4.10 弹窗/面板组件

| 组件 | 触发 | 行为 |
|------|------|------|
| `.lobby-overlay` | 大厅排行榜/历史记录 | 全屏白色 overlay，从右滑入（Vue transition） |
| `.review-overlay` | 复盘着法/信息查看 | 半透明遮罩，居中弹出卡（max-width:520px） |
| `.mobile-panel-sheet` | 移动端着法记录 | 底部弹出，transform 动画，点击遮罩关闭 |
| `.review-popup` | 复盘弹出 | 白底卡片，金色边框，圆角16px |

### 4.11 头像 (Avatar)

```css
/* 大厅头像 */
.avatar     /* 64px 圆形, 金色边框2px, 米黄底, 木色文字28px */

/* 对局头像 */
.ava        /* 44px 圆形(PC) / 32px(移动端), 对手muted/我方金色边框 */
```

### 4.12 卡片

```css
.card               /* 白底, 浅木色边框, 圆角12px, 中等阴影 */
.card--raised       /* 大阴影 */
.card--gold         /* 金色边框 + 外发光 */

/* 对局信息卡 */
.game-info-card     /* 白底卡, .info-row flex space-between */
```

---

## 5. 资源文件清单

### 5.1 SVG 矢量资源（共 38 个）

#### 棋盘（1 个）

| 文件 | 尺寸 | 说明 |
|------|------|------|
| `assets/svg/board.svg` | 540×600 | 完整棋盘（木色底+格线+河界） |

#### 棋子（14 个）— 目录：`assets/svg/pieces/`

**红方（7 枚）**：

| 文件名 | 棋子 | 说明 |
|--------|------|------|
| `red-shuai.svg` | 帥 | 红方将/帅 |
| `red-shi.svg` | 仕 | 红方士 |
| `red-xiang.svg` | 相 | 红方象 |
| `red-ma.svg` | 馬 | 红方马 |
| `red-ju.svg` | 車 | 红方车 |
| `red-pao.svg` | 炮 | 红方炮 |
| `red-bing.svg` | 兵 | 红方兵 |

**黑方（7 枚）**：

| 文件名 | 棋子 | 说明 |
|--------|------|------|
| `black-jiang.svg` | 將 | 黑方将/帅 |
| `black-shi.svg` | 士 | 黑方士 |
| `black-xiang.svg` | 象 | 黑方象 |
| `black-ma.svg` | 馬 | 黑方马 |
| `black-ju.svg` | 車 | 黑方车 |
| `black-pao.svg` | 砲 | 黑方炮 |
| `black-zu.svg` | 卒 | 黑方卒 |

#### UI 图标（23 个）— 目录：`assets/svg/ui/`

| 文件名 | 图标 | 用途 |
|--------|------|------|
| `logo.svg` | 方形Logo | App 图标(120×120) |
| `text-logo.svg` | 横向文字Logo | 标题栏/登录卡(360×96) |
| `btn-bg-normal.svg` | 按钮背景 | 按钮背景图 |
| `icon-settings.svg` | ⚙ | 设置 |
| `icon-back.svg` | ← | 返回 |
| `icon-close.svg` | ✕ | 关闭 |
| `icon-play.svg` | ▶ | 播放 |
| `icon-pause.svg` | ⏸ | 暂停 |
| `icon-prev.svg` | ⏮ | 上一步 |
| `icon-next.svg` | ⏭ | 下一步 |
| `icon-undo.svg` | ↩ | 悔棋 |
| `icon-refresh.svg` | 🔄 | 刷新 |
| `icon-user.svg` | 👤 | 用户 |
| `icon-trophy.svg` | 🏆 | 排行/奖杯 |
| `icon-clock.svg` | 🕐 | 时钟 |
| `icon-check.svg` | ✓ | 确认 |
| `icon-plus.svg` | + | 添加 |
| `icon-exit.svg` | 🚪 | 退出 |
| `icon-fullscreen.svg` | ⛶ | 全屏 |
| `icon-flag.svg` | 🚩 | 认输/旗帜 |
| `icon-sword.svg` | ⚔ | 对战 |
| `icon-import.svg` | 📥 | 导入棋谱 |
| `icon-star.svg` | ⭐ | 收藏 |
| `icon-ai.svg` | 🤖 | AI 对弈 |

### 5.2 CSS 样式模块（14 个）

| 文件 | 行数（约） | 内容 |
|------|----------|------|
| `css/variables.css` | ~155 | 完整设计变量系统（颜色/字体/间距/阴影/棋盘参数） |
| `css/reset.css` | ~20 | 全局重置（box-sizing/margin/字体/链接/按钮） |
| `css/global.css` | ~30 | 通用样式（card/divider/text-center 等） |
| `css/buttons.css` | ~100 | 按钮系统（.btn/.btn-primary/.btn-secondary 等） |
| `css/forms.css` | ~165 | 表单组件（input/checkbox/toggle/select） |
| `css/board.css` | ~180 | 棋盘框架 + 棋子 + 棋盘缩放 |
| `css/pieces.css` | ~80 | 棋子样式（.piece-el 及状态） |
| `css/login.css` | ~50 | 登录界面 |
| `css/lobby.css` | ~80 | 大厅界面（含头像） |
| `css/game.css` | ~375 | 对局界面（含响应式） |
| `css/review.css` | ~350 | 复盘界面（含响应式） |
| `css/settings.css` | ~60 | 设置界面 |
| `css/popups.css` | ~270 | 弹窗/移动端面板（含响应式） |
| `css/main.css` | ~15 | **入口文件**：按顺序 @import 所有模块 |

**CSS 加载顺序**（main.css）：
```
reset.css → variables.css → global.css → buttons.css → forms.css
→ popups.css → board.css → pieces.css → login.css → lobby.css
→ game.css → review.css → settings.css
```

> **注意**：Demo 中所有 CSS 直接内联在 `<style>` 标签中，模块化 CSS 是从内联样式提取独立而成，内容与 Demo 完全一致。

### 5.3 Vue 3 组件（7 个）

| 文件 | 内容 |
|------|------|
| `components/ChessBoard.vue` | 棋盘框架组件（接收 `displayW/displayH` props，含 ResizeObserver 缩放逻辑） |
| `components/ChessPiece.vue` | 单枚棋子组件（.piece-el，接收坐标/尺寸/svg/选中态） |
| `components/PlayerInfo.vue` | 玩家信息组件（.ava + .opp-info + .opp-name + .opp-level） |
| `components/GameTimer.vue` | 倒计时组件（.opp-timer + .opp-timer--warn 闪烁） |
| `components/MoveList.vue` | 着法记录列表（.move-item + .move-red + .move-black） |
| `components/GameControls.vue` | 对局操作按钮（.game-actions-inline：求和/认输/悔棋/退出） |
| `components/PlaybackControls.vue` | 复盘播放控制（.pb-btn + .progress-bar + .speed-btn） |

### 5.4 其他文件

| 文件 | 说明 |
|------|------|
| `demo.html` | **地面真值**：5 界面的完整预览 Demo（Vue 3 CDN + 内联 CSS/JS），所有类名和布局以它为准 |
| `index.html` | 资源预览索引页（展示所有 SVG 棋子/图标/Logo） |

---

## 6. 技术架构建议

### 6.1 推荐技术栈

```
前端框架:     Vue 3 (Composition API) + TypeScript
构建工具:     Vite
状态管理:     Pinia
路由:         Vue Router 4
CSS 方案:     本项目自带 CSS 变量系统（或用 Tailwind CSS 配合自定义主题）
HTTP 客户端:  Axios
WebSocket:    Socket.io (实时对弈通信)
象棋引擎:    wasm 版象棋引擎 或 服务端引擎
包管理:       pnpm (推荐)
```

### 6.2 项目结构建议

```
xiangqi-app/
├── public/
│   └── assets/
│       └── svg/                  ← 本项目的 SVG 资源
│           ├── board.svg
│           ├── pieces/           ← 14 枚棋子
│           └── ui/               ← 23 个图标 + Logo
├── src/
│   ├── assets/
│   │   └── styles/
│   │       ├── variables.css     ← 设计变量
│   │       ├── reset.css
│   │       ├── global.css
│   │       ├── buttons.css
│   │       ├── forms.css
│   │       ├── board.css
│   │       ├── pieces.css
│   │       ├── popups.css
│   │       └── main.css          ← 入口
│   ├── components/
│   │   ├── common/               ← 通用组件
│   │   │   ├── AppButton.vue
│   │   │   ├── AppInput.vue
│   │   │   ├── AppAvatar.vue
│   │   │   └── AppModal.vue
│   │   ├── chess/                ← 棋盘相关
│   │   │   ├── ChessBoard.vue
│   │   │   ├── ChessPiece.vue
│   │   │   └── MoveList.vue
│   │   └── game/                 ← 对局相关
│   │       ├── PlayerInfo.vue
│   │       ├── GameTimer.vue
│   │       ├── GameControls.vue
│   │       └── PlaybackControls.vue
│   ├── views/                    ← 页面
│   │   ├── LoginView.vue
│   │   ├── LobbyView.vue
│   │   ├── GameView.vue
│   │   ├── ReviewView.vue
│   │   └── SettingsView.vue
│   ├── composables/              ← 组合式函数
│   │   ├── useBoardScale.js      ← 棋盘自适应缩放（从 demo.html 提取）
│   │   ├── useGameClock.js       ← 计时逻辑
│   │   ├── useChessEngine.js     ← 象棋引擎封装
│   │   └── useWebSocket.js       ← WebSocket 连接管理
│   ├── stores/                   ← Pinia 状态
│   │   ├── auth.js               ← 用户认证
│   │   ├── game.js               ← 对局状态
│   │   └── settings.js           ← 用户设置
│   ├── router/
│   │   └── index.js              ← 路由定义
│   ├── utils/
│   │   ├── chess.js              ← 象棋规则/走法验证/FEN解析
│   │   └── format.js             ← 格式化工具
│   ├── App.vue
│   └── main.js
├── index.html
├── vite.config.js
├── package.json
└── tsconfig.json
```

### 6.3 路由设计

```
/               → LoginView       (登录/注册/游客)
/lobby          → LobbyView       (游戏大厅)
/game/:roomId   → GameView        (对局)
/game/ai        → GameView        (人机对弈)
/review/:gameId → ReviewView      (棋局复盘)
/settings       → SettingsView    (系统设置)
```

---

## 7. 功能逻辑开发指南

### 7.1 登录/注册模块

**建议方案**：JWT + localStorage

```javascript
// stores/auth.js
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,        // { id, username, avatar, level }
    token: null,
    isGuest: false,
  }),
  actions: {
    async login(username, password) { /* POST /api/auth/login → jwt */ },
    async register(username, password) { /* POST /api/auth/register */ },
    guestLogin() { this.isGuest = true; router.push('/lobby') },
    logout() { /* 清除 token, 跳转登录 */ },
  }
})
```

**游客模式限制**：
- 不保存战绩
- 不参与排行榜
- 不能创建房间（仅可加入）

### 7.2 配对与房间管理

**WebSocket 事件流**：

```
客户端                      服务器
  │                           │
  │── join_queue(playerInfo) ──→  加入匹配队列
  │                           │
  │←── match_found(roomId, opponent) ──  匹配成功
  │                           │
  │── join_room(roomId) ────→  加入房间
  │                           │
  │←── room_joined(players, settings) ──
  │                           │
  │── ready() ──────────────→  准备就绪
  │                           │
  │←── game_start(fen, clock) ──  对局开始
```

**房间设置**：
```javascript
{
  roomId: '8842',
  timeControl: { initial: 900, increment: 5 },  // 15分钟+5秒
  players: [
    { id, username, level, side: 'red' },
    { id, username, level, side: 'black' }
  ]
}
```

### 7.3 象棋引擎集成

**推荐方案**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 服务端引擎（如 Fairy-Stockfish） | 棋力强、不消耗客户端资源 | 需要服务端部署 |
| wasm 版引擎 | 纯前端，离线可用 | 棋力受限于浏览器 |
| 自实现规则校验 | 最轻量 | 需要完整的规则实现 |

**规则校验核心**（自实现时）：
```javascript
// utils/chess.js
export function getValidMoves(board, piece, col, row) {
  // 根据棋子类型返回所有合法走法
  // 需处理: 蹩脚马、塞象眼、将帅对面、移动后是否被将
}

export function isCheck(board, side) {
  // 判断 side 方是否被将军
}

export function isCheckmate(board, side) {
  // 判断 side 方是否被将死（无合法走法且被将军）
}

export function makeMove(board, from, to) {
  // 执行走棋，返回新 board 状态
}

// FEN 字符串解析/生成（用于保存/加载局面）
export function boardToFen(board, sideToMove) { ... }
export function fenToBoard(fen) { ... }
```

### 7.4 走棋流程

```
用户点击棋子
  → selectedPiece = piece            (选中棋子，添加 .sel 类)
  → 计算合法走位                     (高亮可走位置 - 使用 .piece-el 额外类)
  → 用户点击目标格
    → 验证合法性
    → makeMove(board, from, to)
    → 发送走棋到服务器 (WebSocket: make_move)
    → 更新着法记录 (gameMoves.push)
    → 切换 turn
    → selectedPiece = null
```

### 7.5 计时系统

```javascript
// composables/useGameClock.js
export function useGameClock(initialTime, increment) {
  const redTime = ref(initialTime)
  const blackTime = ref(initialTime)
  const turn = ref('red')
  let timer = null

  const start = () => {
    timer = setInterval(() => {
      if (turn.value === 'red') {
        redTime.value = Math.max(0, redTime.value - 1)
        if (redTime.value === 0) emit('timeout', 'red')
      } else {
        blackTime.value = Math.max(0, blackTime.value - 1)
        if (blackTime.value === 0) emit('timeout', 'black')
      }
    }, 1000)
  }

  const switchTurn = () => {
    if (turn.value === 'red') redTime.value += increment
    else blackTime.value += increment
    turn.value = turn.value === 'red' ? 'black' : 'red'
  }

  const stop = () => { clearInterval(timer) }

  return { redTime, blackTime, turn, start, stop, switchTurn }
}
```

### 7.6 复盘播放

```javascript
// composables/usePlayback.js
export function usePlayback(moves, totalMoves) {
  const step = ref(0)
  const playing = ref(false)
  const speed = ref(1)       // 0.5, 1, 2
  let timer = null

  const next = () => { step.value = Math.min(totalMoves, step.value + 1) }
  const prev = () => { step.value = Math.max(0, step.value - 1) }
  const seek = (pct) => { step.value = Math.round(pct * totalMoves) }

  const togglePlay = () => {
    playing.value = !playing.value
    if (playing.value) {
      const interval = 1000 / speed.value
      timer = setInterval(() => {
        if (step.value >= totalMoves) { playing.value = false; clearInterval(timer) }
        else step.value++
      }, interval)
    } else {
      clearInterval(timer)
    }
  }

  const boardAtStep = computed(() => {
    // 根据 step 重建棋盘状态（初始 FEN + 前 step 步走法）
    let board = initialBoard()
    for (let i = 0; i < step.value; i++) {
      board = makeMove(board, moves[i].from, moves[i].to)
    }
    return board
  })

  return { step, playing, speed, next, prev, seek, togglePlay, boardAtStep }
}
```

### 7.7 排行榜

```javascript
// 数据接口
GET /api/leaderboard?page=1&limit=20
Response: {
  ranks: [
    { rank: 1, username: '王天元', level: '特级大师', score: 2847, games: 1234, winRate: 0.72 },
    ...
  ],
  myRank: { rank: 4, ... }
}
```

### 7.8 历史记录

```javascript
// 数据接口
GET /api/history?page=1&limit=20
Response: {
  games: [
    {
      id: 'game_001',
      opponent: { username: '李四海', level: '业余八段' },
      result: 'win',          // 'win' | 'lose' | 'draw'
      date: '2026-06-11T15:30:00Z',
      moves: 47,
      duration: '14:23',
    },
    ...
  ]
}
```

### 7.9 棋盘自适应缩放（关键 composable）

```javascript
// composables/useBoardScale.js
// 从 demo.html 提取的完整逻辑

import { ref, computed, watch, onUnmounted } from 'vue'

const NATIVE_W = 540, NATIVE_H = 600
const CELL_N = 60, PAD_N = 30, PSIZE_N = 48, POFF_N = 24
const MIN_W = 300, MIN_H = 333

export function useBoardScale(boardAreaRef, rawPieces) {
  const scale = ref(1)
  const displayW = ref(540)
  const displayH = ref(600)
  let ro = null

  const calcScale = () => {
    const area = boardAreaRef.value
    if (!area) return
    const availW = area.clientWidth - 48
    const availH = area.clientHeight - 48
    if (availW <= 0 || availH <= 0) return

    let s = Math.min(availW / NATIVE_W, availH / NATIVE_H)
    s = Math.min(s, 1)
    if (NATIVE_W * s < MIN_W) s = MIN_W / NATIVE_W
    if (NATIVE_H * s < MIN_H) s = Math.max(s, MIN_H / NATIVE_H)

    scale.value = s
    displayW.value = Math.round(NATIVE_W * s)
    displayH.value = Math.round(NATIVE_H * s)
  }

  const pieces = computed(() => {
    const s = scale.value
    const cell = CELL_N * s, pad = PAD_N * s
    const poff = POFF_N * s, psize = Math.round(PSIZE_N * s)
    return rawPieces.value.map(p => ({
      ...p,
      x: Math.round(pad + p.col * cell - poff),
      y: Math.round(pad + p.row * cell - poff),
      ds: psize,
    }))
  })

  const observe = () => {
    if (ro) ro.disconnect()
    calcScale()
    ro = new ResizeObserver(calcScale)
    ro.observe(boardAreaRef.value)
  }

  onUnmounted(() => { if (ro) ro.disconnect() })

  return { scale, displayW, displayH, pieces, observe }
}
```

---

## 8. 响应式与移动端适配

### 8.1 断点

| 断点 | 值 | 说明 |
|------|-----|------|
| 移动端 | `≤768px` | 全部使用 `@media (max-width: 768px)` |
| PC 端 | `>768px` | 默认布局 |

### 8.2 各界面移动端适配策略

| 界面 | 适配策略 |
|------|---------|
| **登录** | login-card padding 减小；game-title-img 缩放至 240×64 |
| **大厅** | header 纵向排列；action-btn max-width:100%；链接 flex-wrap |
| **对局** | game-main 改为 column；侧边栏隐藏 → 底部 toggle bar + bottom sheet |
| **复盘** | board-area padding/gap 减小；review-overlay 弹出卡变为底部弹出（border-radius 仅顶部） |
| **设置** | max-width:640px 保持，padding 自适应的 margin |

### 8.3 移动端底部面板交互

```
用户点击 [📜 着法记录]
  → mobilePanel = 'moves'
  → .mobile-panel-overlay.open (显示遮罩)
  → .mobile-panel-sheet.open (从底部滑入)

用户点击遮罩空白处 或 [✕]
  → mobilePanel = ''
  → 面板滑出 + 遮罩隐藏
```

### 8.4 棋盘移动端适配

移动端棋盘使用相同的 ResizeObserver 缩放逻辑，只需调整：
- `.game-board-area` padding 从 24px 减小到 6px
- 最小尺寸限制 `MIN_W=300, MIN_H=333` 保证触摸可用性

---

## 9. 附录

### 9.1 CSS 变量速查表

```css
/* 复制到项目中直接使用 */
:root {
  --color-bg-primary: #FFFBEB;
  --color-bg-secondary: #FFF7D6;
  --color-bg-card: #FFFFFF;
  --color-bg-overlay: rgba(0, 0, 0, 0.45);
  --color-gold: #D97706;
  --color-gold-light: #F59E0B;
  --color-gold-dark: #B45309;
  --color-gold-pressed: #92400E;
  --color-wood-dark: #78350F;
  --color-wood: #92400E;
  --color-wood-light: #D97706;
  --color-wood-bg: #FDE68A;
  --color-text-primary: #451A03;
  --color-text-secondary: #78350F;
  --color-text-tertiary: #A16207;
  --color-text-inverse: #FFFBEB;
  --color-text-muted: #D4A574;
  --color-success: #059669;
  --color-error: #DC2626;
  --color-warning: #D97706;
  --font-serif: 'Noto Serif TC', serif;
  --font-sans: 'Noto Sans TC', sans-serif;
  --font-mono: 'Consolas', monospace;
  --board-w: 540px; --board-h: 600px;
  --cell: 60px; --pad: 30px; --piece-size: 48px;
}
```

### 9.2 常用 CSS 类名速查

```css
/* 布局 */
.game-page, .review-page, .login-page, .lobby-page, .settings-page
.game-topbar, .game-main, .game-center, .game-board-area
.review-header, .review-main, .review-board-area

/* 玩家信息 */
.game-opponent, .game-player
.ava, .opp-info, .opp-name, .opp-level, .opp-timer

/* 棋盘/棋子 */
.board-frame, .board-bg, .piece-el, .piece-el.sel

/* 按钮 */
.btn, .btn-primary, .btn-secondary, .btn-danger, .btn-text
.btn--sm, .btn--lg, .btn--block

/* 着法 */
.game-sidebar, .move-list, .move-item
.move-num, .move-red, .move-black

/* 复盘 */
.playback-controls, .pb-btn, .pb-btn--play
.progress-bar, .progress-fill
.review-toggle-bar, .toggle-item

/* 弹窗 */
.lobby-overlay, .review-overlay, .review-popup
.popup-rank-item, .popup-history-item

/* 移动端 */
.mobile-toggle-bar, .mobile-toggle-btn
.mobile-panel-overlay, .mobile-panel-sheet
```

### 9.3 开发注意事项

1. **CSS 类名命名约定**：使用 BEM 风格简化版，组件前缀 + 状态修饰符（如 `.piece-el.sel`、`.opp-timer--warn`）
2. **所有类名以 Demo 为准**：`demo.html` 是唯一地面真值，新代码的类名必须与其一致
3. **棋盘缩放**：不要用 CSS transform:scale()，使用 JS 动态计算 displayW/displayH + 棋子坐标
4. **Vue Transition**：弹窗使用 `<transition name="overlay">`，动画定义在 popups.css 中
5. **字体加载**：确保引入 Google Fonts（Noto Serif TC + Noto Sans TC），或配置本地字体回退
6. **棋盘 SVG 尺寸**：board.svg 为 540×600，不要修改其 viewBox，缩放全部在 JS 层处理
7. **移动端断点**：统一使用 `@media (max-width: 768px)`，不要混用多个断点
8. **红黑方颜色约定**：红方使用 `#C53030`（朱红），黑方使用 `#2D3748`（深灰蓝）
