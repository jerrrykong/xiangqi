# UI 升级计划 — 楚漢爭鋒

> 版本：v1.0 | 创建日期：2026-06-14 | 状态：执行中

---

## 1. 升级目标

将现有项目 UI 从「Element Plus 默认 + 简单木色系」升级为「完整中国传统木质风格设计系统」，基于 `xiangqi-assets/` 提供的设计稿、CSS 模块和 SVG 资源。

### 核心变更

| 维度 | 现状 | 目标 |
|------|------|------|
| 设计系统 | 10 个 CSS 变量，无规范 | 80+ CSS 变量，14 个模块化 CSS 文件 |
| CSS 架构 | 单文件 `main.css` | 14 个模块化 CSS 文件，`@import` 顺序加载 |
| 棋盘渲染 | SVG 内联绘制线+格，CSS div 做棋子 | `board.svg` 背景图 + SVG 图片棋子（14 枚） |
| 棋子渲染 | CSS 渐变圆 + 文字 | SVG 图片（中国传统木质阴刻风格） |
| 按钮系统 | Element Plus 默认 | 自定义 `.btn-primary/.btn-secondary/.btn-danger/.btn-text` |
| 表单系统 | `el-form` + `el-input` | 自定义 `.form-input/.form-group` |
| 弹窗系统 | `el-dialog` | 自定义 `.lobby-overlay/.review-popup` + Vue Transition |
| 响应式断点 | 1024px，两套 HTML | 768px，同一套 HTML + CSS 媒体查询 |
| UI 组件库 | Element Plus 完整引入 | 完全移除，全部自定义 |

---

## 2. 执行阶段与任务清单

### 阶段一：基础设施迁移（设计系统 + 资源）

> 目标：替换 CSS 设计系统、迁移 SVG 资源、移除 Element Plus

| 编号 | 任务 | 涉及文件 | 说明 |
|------|------|---------|------|
| 1.1 | 复制 SVG 资源到 public 目录 | `cmd/web/public/assets/svg/` | 复制 `xiangqi-assets/assets/svg/` 全部内容（board.svg、14 枚棋子、23 个 UI 图标） |
| 1.2 | 替换 CSS 设计系统 | `cmd/web/src/styles/` | 用 `xiangqi-assets/css/` 14 个模块文件替换现有 `main.css`，保留变量兼容映射 |
| 1.3 | 更新 `main.ts` | `cmd/web/src/main.ts` | 移除 Element Plus 引入、图标注册；CSS 入口改为新的 `main.css` |
| 1.4 | 更新 `App.vue` | `cmd/web/src/App.vue` | 确保根组件不含 Element Plus 残留 |
| 1.5 | 兼容性变量映射 | `cmd/web/src/styles/_compat.css` | 新增旧变量名 → 新变量名的映射，确保现有页面过渡期可用 |

### 阶段二：核心组件重构

> 目标：重写棋盘组件、新建对局辅助组件

| 编号 | 任务 | 涉及文件 | 说明 |
|------|------|---------|------|
| 2.1 | 新建 `ChessPiece.vue` | `cmd/web/src/components/chess/ChessPiece.vue` | SVG 图片棋子组件，接收坐标/尺寸/svg/选中态 |
| 2.2 | 重构 `ChessBoard.vue` | `cmd/web/src/components/chess/ChessBoard.vue` | 改用 `board.svg` 背景图 + ChessPiece SVG 图片棋子，适配新缩放逻辑（JS 动态计算 displayW/displayH） |
| 2.3 | 新建 `PlayerInfo.vue` | `cmd/web/src/components/game/PlayerInfo.vue` | 玩家信息组件（.ava + .opp-info + .opp-name + .opp-level），集成本地 GameTimer |
| 2.4 | 新建 `GameTimer.vue` | `cmd/web/src/components/game/GameTimer.vue` | 倒计时组件（.opp-timer + .opp-timer--warn 闪烁） |
| 2.5 | 新建 `MoveList.vue` | `cmd/web/src/components/chess/MoveList.vue` | 着法记录列表（.move-item + .move-red + .move-black） |
| 2.6 | 新建 `GameControls.vue` | `cmd/web/src/components/game/GameControls.vue` | 对局操作按钮行（.game-actions-inline：求和/认输/悔棋/退出） |
| 2.7 | 新建 `PlaybackControls.vue` | `cmd/web/src/components/game/PlaybackControls.vue` | 复盘播放控制（.pb-btn + .progress-bar + .speed-btn），暂供复盘页使用 |

### 阶段三：页面 UI 升级

> 目标：逐页替换 Element Plus 组件为新设计

| 编号 | 任务 | 涉及文件 | 说明 |
|------|------|---------|------|
| 3.1 | 升级 `Splash.vue` | `cmd/web/src/pages/Splash.vue` | 适配新设计系统变量（去旧变量），.btn-primary/.btn-secondary 替换 |
| 3.2 | 升级 `Login.vue` | `cmd/web/src/pages/Login.vue` | 木质风格卡片 + text-logo SVG + .form-input + .btn-primary + .btn-secondary，移除 `el-form`/`el-input` |
| 3.3 | 升级 `Register.vue` | `cmd/web/src/pages/Register.vue` | 同登录风格，移除 `el-form`/`el-input`/`el-button` |
| 3.4 | 升级 `Lobby.vue` | `cmd/web/src/pages/Lobby.vue` | 单列居中操作卡 + SVG 图标 + .lobby-action-btn + overlay 弹窗（排行榜/历史），移除 `el-button`/`el-dialog`/`el-tag` |
| 3.5 | 升级 `RoomList.vue` | `cmd/web/src/pages/RoomList.vue` | 适配新设计系统，自定义按钮替代 `el-button`/`el-tag`/`el-pagination` |
| 3.6 | 升级 `Game.vue` | `cmd/web/src/pages/Game.vue` | 新布局（topbar + center + sidebar）+ PlayerInfo/GameTimer/MoveList/GameControls 组件集成 + 移动端 bottom sheet，移除 `el-button`/`el-dialog` |

### 阶段四：新页面 + 收尾

| 编号 | 任务 | 涉及文件 | 说明 |
|------|------|---------|------|
| 4.1 | 新建 `Settings.vue` | `cmd/web/src/pages/Settings.vue` | 设置页框架（对局设置/账号/关于/退出登录），.settings-page 布局 |
| 4.2 | 新建 `Review.vue` | `cmd/web/src/pages/Review.vue` | 复盘页框架（棋盘 + PlaybackControls + toggle-bar），.review-page 布局 |
| 4.3 | 注册新路由 | `cmd/web/src/router/index.ts` | 添加 `/settings` 和 `/review` 路由 |
| 4.4 | 移除兼容性映射 | `cmd/web/src/styles/_compat.css` | 确认所有旧变量引用已清理，删除兼容文件 |
| 4.5 | 全局响应式验证 | 所有页面 | 确认 768px 断点，移动端适配 |

---

## 3. 依赖关系

```
阶段一（基础设施）
  ├── 1.1 SVG 资源 ←── 无依赖
  ├── 1.2 CSS 系统 ←── 无依赖
  ├── 1.3 main.ts ←── 1.2
  ├── 1.4 App.vue ←── 1.3
  └── 1.5 兼容映射 ←── 1.2

阶段二（核心组件） ←── 阶段一完成
  ├── 2.1 ChessPiece ←── 1.1（SVG 资源）
  ├── 2.2 ChessBoard ←── 2.1 + 1.2（board.css/pieces.css）
  ├── 2.3 PlayerInfo ←── 2.4
  ├── 2.4 GameTimer ←── 1.2
  ├── 2.5 MoveList ←── 1.2
  ├── 2.6 GameControls ←── 1.2
  └── 2.7 PlaybackControls ←── 1.2

阶段三（页面升级） ←── 阶段二完成
  ├── 3.1 Splash ←── 1.2
  ├── 3.2 Login ←── 1.2 + 1.3
  ├── 3.3 Register ←── 同 3.2
  ├── 3.4 Lobby ←── 1.2 + 1.3
  ├── 3.5 RoomList ←── 1.2 + 1.3
  └── 3.6 Game ←── 2.2~2.6

阶段四（新页面+收尾） ←── 阶段三完成
  └── 4.1~4.5 ←── 阶段三
```

---

## 4. CSS 变量兼容映射

旧项目使用的变量名 → 新设计系统变量名的映射关系：

| 旧变量名 | 新变量名 | 说明 |
|----------|---------|------|
| `--color-wood-50` | `--color-bg-tertiary` (#FEF3C7) | 近似替换 |
| `--color-wood-100` | `--color-bg-primary` (#FFFBEB) | 米黄主背景 |
| `--color-wood-200` | `--color-bg-secondary` (#FFF7D6) | 浅米黄 |
| `--color-wood-300` | `--color-wood-bg` (#FDE68A) | 木纹底色 |
| `--color-wood-400` | `--color-gold-light` (#F59E0B) | 金色浅 |
| `--color-wood-500` | `--color-wood-light` (#D97706) | 浅木色 |
| `--color-wood-600` | `--color-wood` (#92400E) | 胡桃木 |
| `--color-wood-700` | `--color-wood-dark` (#78350F) | 深胡桃木 |
| `--color-wood-800` | `--color-wood-dark` (#78350F) | 深胡桃木（近似） |
| `--color-wood-900` | `--color-wood-dark` (#78350F) | 深胡桃木（近似） |
| `--color-piece-red` | `--color-piece-red-text` (#8B2500) | 朱砂红 |
| `--color-piece-black` | `--color-piece-black-text` (#F0D68A) | 奶油金 |

> 注意：新设计中棋子改为 SVG 图片，`--color-piece-red/black` 不再用于棋子文字，但仍可用于着法记录等文字场景。映射表中 `--color-piece-red` → `#C53030`（朱红，着法文字用）。

---

## 5. Element Plus 移除策略

### 需要替换的 Element Plus 组件

| Element Plus 组件 | 替换方案 |
|-------------------|---------|
| `el-button` | `.btn` + `.btn-primary/.btn-secondary/.btn-danger/.btn-text` |
| `el-input` | `.form-input` |
| `el-form` / `el-form-item` | `.form-group` + `.form-label` + `.form-input` + 手动验证 |
| `el-dialog` | `.lobby-overlay` / `.review-overlay` + Vue Transition |
| `el-tag` | 自定义 `.status-tag` 样式 |
| `el-pagination` | 自定义分页组件 |
| `el-slider` | 自定义滑块 |
| `ElMessage` | 自定义 Toast 通知组件 |
| `ElMessageBox` | 自定义 Confirm 对话框组件 |

### 新建通用 UI 组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `AppToast` | `cmd/web/src/components/common/AppToast.vue` | Toast 通知（替代 `ElMessage`） |
| `AppConfirm` | `cmd/web/src/components/common/AppConfirm.vue` | 确认对话框（替代 `ElMessageBox`） |

---

## 6. 技术要点

### 6.1 棋盘缩放机制变更

**现有**：CSS `transform: scale()` 缩放整个棋盘容器

**新设计**：JS 动态计算 `displayW/displayH`，棋子坐标 = `col × cell × scale + pad × scale - poff × scale`

```javascript
const NATIVE_W = 540, NATIVE_H = 600
const CELL_N = 60, PAD_N = 30, PSIZE_N = 48, POFF_N = 24
const MIN_W = 300, MIN_H = 333

// ResizeObserver 监听 .game-board-area → 动态设置 .board-frame 的 width/height
// 棋子通过 computed 计算绝对定位 left/top
```

### 6.2 表单验证方案

移除 `el-form` 的规则验证后，使用手动验证：

```typescript
function validateForm(): { valid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {}
  if (!form.username || form.username.length < 4) errors.username = '用户名至少4个字符'
  if (!form.password || form.password.length < 8) errors.password = '密码至少8个字符'
  return { valid: Object.keys(errors).length === 0, errors }
}
```

### 6.3 弹窗交互方案

替代 `el-dialog`，使用自定义 overlay：

```html
<transition name="overlay">
  <div v-if="showOverlay" class="lobby-overlay" @click.self="showOverlay = false">
    <div class="overlay-header">
      <h3>标题</h3>
      <button class="overlay-close" @click="showOverlay = false">✕</button>
    </div>
    <div class="overlay-body">内容</div>
  </div>
</transition>
```

---

## 7. 风险与注意事项

1. **Element Plus 移除是全局性的**：所有页面必须同时升级，否则会出现样式断裂。建议阶段一完成后立即连续完成阶段三。
2. **棋盘重构影响游戏逻辑**：`ChessBoard.vue` 的 props/events 接口需要保持与 `Game.vue` 的兼容，或者同步修改。
3. **音效系统不变**：`utils/sound.ts` 不受 UI 升级影响。
4. **Store 层不变**：4 个 Pinia Store（auth/game/room/match）的业务逻辑不变，仅页面消费方式调整。
5. **WebSocket 层不变**：ws/client、ws/router、ws/handlers 不受影响。

---

## 8. 验收标准

- [ ] Element Plus 完全移除（`package.json` 无依赖、`main.ts` 无引入）
- [ ] 所有页面使用新设计系统的 CSS 变量和类名
- [ ] 棋盘使用 `board.svg` 背景 + SVG 图片棋子
- [ ] 所有弹窗使用自定义 overlay 组件
- [ ] 所有表单使用 `.form-input` + 手动验证
- [ ] 响应式断点统一为 768px
- [ ] 对局页 PC 端新布局（topbar + center + sidebar）
- [ ] 对局页移动端适配（底部面板 + toggle bar）
- [ ] Settings 页和 Review 页框架可访问
- [ ] 所有现有业务功能正常（登录/注册/大厅/对局/认输/求和等）
