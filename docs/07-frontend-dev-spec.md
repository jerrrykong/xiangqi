# 楚汉争锋 — 前端开发规范与页面设计指引

> 本文档基于当前工程代码的实际结构与模式编写，确保新功能与现有代码风格完全一致。

---

## 1. 技术栈与核心依赖

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue 3 | Composition API + `<script setup>` |
| 状态管理 | Pinia | defineStore + setup 函数式 |
| 路由 | Vue Router 4 | createWebHistory |
| 构建 | Vite | base: `/xiangqi/` |
| 语言 | TypeScript | strict mode |
| UI 组件 | **自建**（无 Element Plus） | 全局 CSS + scoped |
| 通信 | WebSocket | 自建 WSClient + MessageRouter |

### 禁止事项

- **禁止**引入 Element Plus / Ant Design 等第三方 UI 库
- **禁止**引入新的 CSS 框架（Tailwind / Bootstrap 等）
- **禁止**在代码中使用 emoji 作为 UI 图标（统一使用 SVG）
- **禁止**使用内联 `style=""` 属性（除非动态计算的定位尺寸）
- 新增依赖须经团队评审

---

## 2. 目录结构与职责划分

```
cmd/web/src/
├── main.ts                  # 入口：创建 app、注册 pinia/router、导入全局样式
├── App.vue                  # 根组件：注册 WS handler、监听断连、预加载音效
├── router/index.ts          # 路由配置 + beforeEach 守卫（认证 & WS 状态）
├── pages/                   # 页面级组件（每个对应一条路由）
│   ├── Splash.vue           # 启动页
│   ├── Login.vue            # 登录
│   ├── Register.vue         # 注册
│   ├── Lobby.vue            # 大厅
│   ├── RoomList.vue         # 房间列表
│   ├── Game.vue             # 对局
│   ├── Review.vue           # 复盘
│   └── Settings.vue         # 设置
│
├── components/              # 可复用组件（按领域分子目录）
│   ├── chess/               # 棋局领域
│   │   ├── ChessBoard.vue   # 棋盘渲染
│   │   ├── ChessPiece.vue   # 单个棋子
│   │   ├── MoveList.vue     # 着法列表
│   ├── game/                # 对局 UI
│   │   ├── GameControls.vue # 操作按钮组
│   │   ├── GameTimer.vue    # 计时器
│   │   ├── PlayerInfo.vue   # 玩家信息
│   │   ├── PlaybackControls.vue # 复盘播放控制
│   ├── common/              # 公共交互组件
│   │   ├── AppToast.vue     # Toast 通知
│   │   ├── AppConfirm.vue   # 确认对话框
│   │   ├── ui.ts            # 编程式调用（showToast / showConfirm）
│
├── stores/                  # Pinia 状态管理
│   ├── auth.ts              # 认证 & 用户状态
│   ├── game.ts              # 棋局状态 & 走棋逻辑
│   ├── room.ts              # 房间状态
│   ├── match.ts             # 匹配状态
│
├── ws/                      # WebSocket 通信层
│   ├── client.ts            # WSClient 类（连接/重连/心跳）
│   ├── request.ts           # 请求-响应匹配（seq → Promise）
│   ├── router.ts            # 消息路由（type → handler[]）
│   ├── types.ts             # 协议类型定义（WSMsgType / WSRespType）
│   ├── handlers/            # 消息处理器（按领域拆分）
│       ├── auth.handler.ts
│       ├── game.handler.ts
│       ├── room.handler.ts
│       ├── match.handler.ts
│       ├── user.handler.ts
│
├── types/                   # 业务类型定义
│   ├── chess.ts             # 棋子编码、棋盘配置、走法类型
│   ├── api.ts               # API 交互类型
│
├── utils/                   # 工具函数
│   └── sound.ts             # 音效管理器
│
├── styles/                  # 全局样式（模块化 CSS）
│   ├── main.css             # 入口：@import 顺序导入所有模块
│   ├── reset.css            # 全局重置
│   ├── variables.css        # 设计变量系统（颜色、字号、间距、阴影等）
│   ├── global.css           # 通用类（.avatar / .card / .divider / .flex-*）
│   ├── buttons.css          # 按钮系统（.btn 系列）
│   ├── forms.css            # 表单控件（.form-input / .toggle / .form-select）
│   ├── popups.css           # 弹窗/弹出面板（.lobby-overlay / .review-overlay / .mobile-panel）
│   ├── board.css            # 棋盘样式
│   ├── pieces.css           # 棋子样式
│   ├── login.css            # 登录页样式
│   ├── lobby.css            # 大厅页样式
│   ├── game.css             # 对局页样式
│   ├── review.css           # 复盘页样式
│   ├── settings.css         # 设置页样式
│   ├── _compat.css          # 旧变量名兼容映射（过渡期）
│
├── auto-imports.d.ts        # AutoImport 生成
├── components.d.ts          # Components 生成
│
cmd/web/public/              # 静态资源
└── assets/
    ├── svg/
    │   ├── board.svg        # 棋盘背景
    │   ├── pieces/          # 14 个棋子 SVG（按编码命名）
    │   ├── ui/              # UI 图标 SVG（icon-*.svg）
    ├── wav/                 # 音效文件
```

### 新增文件的归属原则

| 类型 | 放在哪里 | 命名规范 |
|------|---------|---------|
| 新页面 | `pages/` | PascalCase.vue |
| 新组件 | `components/{领域}/` | PascalCase.vue |
| 新 Store | `stores/` | camelCase.ts |
| 新 WS handler | `ws/handlers/` | `{领域}.handler.ts` |
| 新类型 | `types/` | camelCase.ts |
| 新样式 | `styles/` | kebab-case.css + 在 main.css 注册 |
| 新 SVG 图标 | `public/assets/svg/ui/` | `icon-{名称}.svg` |
| 新棋子 SVG | `public/assets/svg/pieces/` | 按棋子编码命名 |

---

## 3. Vue 组件编写规范

### 3.1 `<script setup>` 模板

每个组件必须遵循以下结构顺序：

```vue
/**
 * ComponentName — 简要描述
 * 详细说明（如有必要）
 *
 * @prop propA - 属性说明
 * @prop propB - 属性说明
 */
<script setup lang="ts">
// 1. 常量
const baseUrl = import.meta.env.BASE_URL

// 2. Props & Emits
defineProps<{ ... }>()
const emit = defineEmits<{ ... }>()

// 3. Store 引入
const someStore = useSomeStore()

// 4. Ref / Reactive
const localState = ref(...)

// 5. Computed
const derived = computed(() => ...)

// 6. Watch
watch(() => ..., (val) => { ... })

// 7. 生命周期
onMounted(() => { ... })
onUnmounted(() => { ... })

// 8. 方法（按调用顺序或功能分组）
function handleSomething() { ... }
</script>

<template>
  ...
</template>

<style scoped>
...
</style>
```

### 3.2 关键规则

1. **baseUrl 常量**：凡引用 `public/assets/` 下资源的组件，必须在 `<script setup>` 顶部声明：
   ```ts
   const baseUrl = import.meta.env.BASE_URL  // '/xiangqi/'
   ```
   SVG 图标路径必须通过 `baseUrl` 拼接：
   ```html
   <img :src="baseUrl + 'assets/svg/ui/icon-play.svg'" alt="" class="btn-icon-xs" />
   ```
   **禁止**使用相对路径或硬编码 `/xiangqi/`。

2. **Props 定义**：使用 TypeScript 泛型语法 `defineProps<{}>()`，不用对象语法。
   ```ts
   // ✅ 正确
   defineProps<{
     phase: 'playing' | 'finished' | 'ready'
     canRematch?: boolean
   }>()

   // ❌ 禁止
   defineProps({
     phase: { type: String, required: true },
     canRematch: { type: Boolean, default: false },
   })
   ```

3. **Emits 定义**：使用类型化签名语法：
   ```ts
   const emit = defineEmits<{
     (e: 'draw'): void
     (e: 'resign'): void
     (e: 'exit'): void
   }>()
   ```

4. **JSDoc 注释**：组件文件顶部必须有 JSDoc 注释块，说明用途和关键 props。方法必须有简要注释。

5. **scoped 样式**：所有组件样式必须 `<style scoped>`，页面级样式也用 scoped（除非需要影响全局弹窗等子组件）。

6. **禁止在模板中使用 emoji**：所有图标统一用 SVG，参照现有组件的模式。

---

## 4. 样式规范

### 4.1 CSS 变量体系

**必须**使用 `variables.css` 中定义的变量，禁止硬编码颜色/字号/间距值。

#### 颜色系统

| 类别 | 变量 | 值 | 用途 |
|------|------|----|------|
| 主背景 | `--color-bg-primary` | `#FFFBEB` | 页面底色 |
| 次级背景 | `--color-bg-secondary` | `#FFF7D6` | 区域/卡片次底色 |
| 三级背景 | `--color-bg-tertiary` | `#FEF3C7` | 最浅区域底色 |
| 卡片 | `--color-bg-card` | `#FFFFFF` | 卡片白色底 |
| 遮罩 | `--color-bg-overlay` | `rgba(0,0,0,0.45)` | 弹窗背景遮罩 |
| 金色主强调 | `--color-gold` | `#D97706` | 按钮/高亮/选中 |
| 金色浅 | `--color-gold-light` | `#F59E0B` | hover态/边框 |
| 金色深 | `--color-gold-dark` | `#B45309` | active态/边框深 |
| 金色按压 | `--color-gold-pressed` | `#92400E` | pressed态 |
| 深木 | `--color-wood-dark` | `#78350F` | 标题/重要文字 |
| 木色 | `--color-wood` | `#92400E` | 主文字/边框 |
| 中木 | `--color-wood-medium` | `#B45309` | 次文字 |
| 浅木 | `--color-wood-light` | `#D97706` | 分割线/淡边框 |
| 木纹底 | `--color-wood-bg` | `#FDE68A` | hover背景 |
| 主文字 | `--color-text-primary` | `#451A03` | 正文标题 |
| 次文字 | `--color-text-secondary` | `#78350F` | 辅助说明 |
| 三级文字 | `--color-text-tertiary` | `#A16207` | 标签/注释 |
| 反色文字 | `--color-text-inverse` | `#FFFBEB` | 金色按钮上的文字 |
| 禁用文字 | `--color-text-muted` | `#D4A574` | placeholder/禁用态 |
| 成功 | `--color-success` | `#059669` | 成功提示 |
| 警告 | `--color-warning` | `#D97706` | 警告提示 |
| 错误 | `--color-error` | `#DC2626` | 错误提示 |
| 信息 | `--color-info` | `#2563EB` | 信息提示 |

#### 字体系统

| 变量 | 值 | 使用场景 |
|------|----|---------|
| `--font-serif` | `'Noto Serif TC', ...` | 标题、按钮文字、玩家名称 |
| `--font-sans` | `'Noto Sans TC', ...` | 正文、辅助信息、表单 |
| `--font-mono` | `'JetBrains Mono', ...` | 计时器、着法编号、分数 |
| `--font-logo` | `'Noto Serif TC', KaiTi, ...` | Logo 文字 |
| `--font-piece` | `'STXingkai', ...` | 棋子刻字（SVG 内使用） |

#### 字号层级

```
--text-xs    0.75rem (12px) — 辅助信息、标签
--text-sm    0.875rem (14px) — 次要文字、按钮小尺寸
--text-base  1rem (16px) — 正文
--text-lg    1.125rem (18px) — 子标题
--text-xl    1.25rem (20px) — 标题
--text-2xl   1.5rem (24px) — 大标题/计时器
--text-3xl   1.875rem (30px) — 页面标题
--text-4xl   2.25rem (36px) — Logo/主标题
```

#### 字重

```
--weight-light     300
--weight-normal    400
--weight-medium    500
--weight-semibold  600
--weight-bold      700
```

#### 间距系统（4px 基准）

```
--space-1   0.25rem (4px)
--space-2   0.5rem (8px)
--space-3   0.75rem (12px)
--space-4   1rem (16px)
--space-5   1.25rem (20px)
--space-6   1.5rem (24px)
--space-8   2rem (32px)
--space-10  2.5rem (40px)
--space-12  3rem (48px)
--space-16  4rem (64px)
--space-20  5rem (80px)
```

#### 圆角

```
--radius-xs   4px — 小元素
--radius-sm   6px — 按钮/输入框小尺寸
--radius-md   8px — 默认按钮/输入框
--radius-lg   12px — 卡片
--radius-xl   16px — 大卡片/弹窗
--radius-2xl  24px — 登录卡片
--radius-full 9999px — 圆形/胶囊
```

#### 阴影

```
--shadow-sm    小阴影 — 按钮/卡片默认
--shadow-md    中阴影 — 卡片hover
--shadow-lg    大阴影 — 弹窗
--shadow-xl    最大阴影 — 弹窗/面板
--shadow-inner 内阴影 — pressed态
--shadow-piece         棋子默认阴影
--shadow-piece-raised  棋子hover阴影
```

#### 过渡动画

```
--transition-fast    150ms ease — hover/小交互
--transition-normal  250ms ease — 展开/面板
--transition-slow    400ms ease — 页面切换
```

#### 层级（z-index）

```
--z-dropdown        100
--z-sticky          200
--z-modal-backdrop  300
--z-modal           400
--z-tooltip         500
--z-toast           600
```

#### 断点

```
--bp-mobile   390px
--bp-tablet   768px   ← 响应式核心断点
--bp-desktop  1024px
--bp-wide     1440px
```

### 4.2 样式归属原则

| 样式类型 | 写在哪里 | 说明 |
|----------|---------|------|
| 设计变量 | `variables.css` | 颜色、字号、间距、阴影等 |
| 全局重置 | `reset.css` | box-sizing、字体、滚动条 |
| 公共组件类 | `global.css` | `.avatar` `.card` `.divider` `.flex-*` `.text-*` |
| 按钮 | `buttons.css` | `.btn` `.btn-primary` `.btn-secondary` `.btn-danger` `.btn-text` `.btn--sm` `.btn--lg` `.btn--block` |
| 表单控件 | `forms.css` | `.form-input` `.toggle` `.toggle-track` `.form-select` `.form-checkbox` `.form-group` `.form-label` `.form-hint` `.form-error` |
| 弹窗/面板 | `popups.css` | `.lobby-overlay` `.review-overlay` `.mobile-panel` `.popup-rank-item` `.popup-history-item` |
| 页面布局 | `{page-name}.css` | 如 `lobby.css` `game.css` `settings.css` |
| 棋盘棋子 | `board.css` `pieces.css` | 棋盘框架、棋子定位与动画 |

**新增页面的样式**：
1. 创建 `styles/{page-name}.css`
2. 在 `styles/main.css` 中按顺序追加 `@import './{page-name}.css';`
3. 页面组件内 `<style scoped>` 写仅该页面特有的样式

**新增公共组件的样式**：
1. 放入对应的公共 CSS 文件（`buttons.css` / `forms.css` / `popups.css`）
2. 如果是新类型组件，创建独立的公共 CSS 文件并在 `main.css` 注册

### 4.3 CSS 命名规范

- **BEM 简化变体**：`block-element` + `block--modifier`
  - 例：`.btn-primary` `.btn--sm` `.game-topbar` `.opp-name`
- **页面级类名**：以页面名前缀（`.lobby-*` `.game-*` `.settings-*` `.review-*` `.login-*`）
- **组件级类名**：以组件功能名前缀（`.ava` `.piece-el` `.move-item` `.pb-btn`）
- **状态修饰**：`.active` `.sel` `.--warn` `.disabled` `.open`
- **功能色类**：`.toast-success` `.popup-result.win` `.turn-red`

---

## 5. 公共组件库

### 5.1 按钮系统

```html
<!-- 主要按钮 -->
<button class="btn btn-primary">操作</button>
<button class="btn btn-primary btn--sm">小按钮</button>

<!-- 次要按钮 -->
<button class="btn btn-secondary">操作</button>

<!-- 危险按钮 -->
<button class="btn btn-danger btn--block">退出登录</button>

<!-- 文字按钮 -->
<button class="btn btn-text">取消</button>

<!-- 带 SVG 图标 -->
<button class="btn btn-primary btn--sm">
  <img :src="baseUrl + 'assets/svg/ui/icon-play.svg'" alt="" class="btn-icon-xs" />
  开始
</button>
```

按钮图标尺寸规范：
- 小按钮 `btn--sm`：图标 `16px`（`.btn-icon-xs`）
- 默认按钮：图标 `20px`（`.btn-icon-sm`）
- 大按钮 `btn--lg`：图标 `24px`

### 5.2 Toggle 开关

```html
<label class="toggle">
  <input type="checkbox" v-model="someBoolean" />
  <span class="toggle-track"></span>
</label>
```

**禁止**在页面 scoped 样式中重写 `.toggle` / `.toggle-track` 的核心样式，使用全局 `forms.css` 中的定义。

### 5.3 表单输入

```html
<div class="form-group">
  <label class="form-label">标签</label>
  <input class="form-input" v-model="value" placeholder="提示" />
  <span class="form-hint">辅助说明</span>
  <span class="form-error">错误提示</span>
</div>
```

### 5.4 Toast / Confirm

```ts
import { showToast, showConfirm } from '@/components/common/ui'

// Toast
showToast('操作成功', 'success')       // success | error | warning | info
showToast('操作失败', 'error', 3000)    // 可自定义时长

// Confirm（Promise 化）
const ok = await showConfirm('确定要退出吗？', '提示', {
  type: 'warning',           // warning | danger | info
  confirmText: '确定',
  cancelText: '取消',
})
```

### 5.5 全屏 Overlay（二级界面）

用于排行榜、历史对局、PvE 难度选择等全屏二级界面：

```html
<div v-if="showOverlay" class="lobby-overlay" @click.self="showOverlay = false">
  <div class="overlay-header">
    <h3 class="overlay-title">
      <img :src="baseUrl + 'assets/svg/ui/icon-xxx.svg'" alt="" class="title-icon" />
      标题文字
    </h3>
    <button class="overlay-close" @click="showOverlay = false">
      <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
    </button>
  </div>
  <div class="overlay-body">
    <!-- 内容区域，自动 overflow-y: auto -->
  </div>
  <div class="overlay-footer">
    <button class="btn btn-secondary" @click="...">取消</button>
    <button class="btn btn-primary" @click="...">确定</button>
  </div>
</div>
```

配合 `<Transition>` 动画：
```html
<Transition name="overlay">
  <div v-if="showOverlay" class="lobby-overlay">...</div>
</Transition>
```

### 5.6 居中弹窗（对话式）

用于确认框、小型设置面板等居中弹出内容：

```html
<div v-if="showPopup" class="review-overlay" @click.self="showPopup = false">
  <div class="review-popup">
    <div class="popup-header">
      <h3 class="popup-title">标题</h3>
      <button class="popup-close" @click="showPopup = false">
        <img :src="baseUrl + 'assets/svg/ui/icon-close.svg'" alt="关闭" />
      </button>
    </div>
    <div class="popup-body">...</div>
  </div>
</div>
```

### 5.7 头像

```html
<!-- 全局 .avatar 类 -->
<div class="avatar">
  <img :src="baseUrl + 'assets/svg/ui/icon-user.svg'" alt="" class="avatar-icon" />
  <span class="avatar-text">{{ name.charAt(0) }}</span>
</div>

<!-- 尺寸变体 -->
<div class="avatar avatar--sm">...</div>   <!-- 40px -->
<div class="avatar avatar--lg">...</div>   <!-- 80px -->
```

### 5.8 卡片

```html
<div class="card">默认卡片</div>
<div class="card card--raised">浮起卡片</div>
<div class="card card--gold">金色边框卡片</div>
```

### 5.9 分割线

```html
<div class="divider"></div>
```

---

## 6. 页面设计指引

### 6.1 页面布局模式

#### 单列居中页面（Lobby / Settings / Login）

```
.page-name {
  max-width: var(--max-width-content);  /* 或 640px 等合适值 */
  margin: 0 auto;
  padding: var(--space-6);
  min-height: 100vh;
  background: var(--color-bg-primary);
}
```

#### 全高度页面（Game / Review）

```
.page-name {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 52px);
  max-width: var(--max-width-content);
  margin: 0 auto;
  overflow: hidden;
  background: var(--color-bg-primary);
}
```

#### 页面顶部栏

```
.page-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 24px;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-wood-light);
  flex-shrink: 0;
}
```

### 6.2 移动端响应式策略

- **核心断点**：`@media (max-width: 768px)`
- 所有页面必须在 768px 断点下有适配样式
- 390px 以下的小屏幕如有必要需额外处理
- 棋盘/弹窗等尺寸需动态缩放

常见移动端调整：
```css
@media (max-width: 768px) {
  /* 缩小间距和字号 */
  .page-name { padding: var(--space-4); }
  .page-title { font-size: var(--text-base); }

  /* 隐藏桌面端侧边栏 */
  .desktop-sidebar { display: none; }

  /* 水平布局改为垂直 */
  .flex-row-layout { flex-direction: column; }

  /* 弹窗改为底部滑出 */
  .review-popup { border-radius: 16px 16px 0 0; }
}
```

### 6.3 新页面模板

创建新页面时的标准结构：

```vue
/**
 * NewPage — 新页面简要描述
 * 
 * 布局说明
 */
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showToast, showConfirm } from '@/components/common/ui'

const router = useRouter()
const baseUrl = import.meta.env.BASE_URL
const authStore = useAuthStore()

// 页面状态
const isLoading = ref(false)

// 方法
function handleAction() {
  // ...
}
</script>

<template>
  <div class="newpage-page">
    <!-- 顶部栏（如有） -->
    <div class="newpage-header">
      <button class="btn btn-text" @click="router.back()">
        <img :src="baseUrl + 'assets/svg/ui/icon-back.svg'" alt="" class="btn-icon-sm" />
        返回
      </button>
      <h1 class="newpage-title">页面标题</h1>
    </div>

    <!-- 内容区域 -->
    <div class="newpage-body">
      ...
    </div>
  </div>
</template>

<style scoped>
.newpage-page {
  max-width: var(--max-width-content);
  margin: 0 auto;
  padding: var(--space-6);
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.newpage-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) 0;
  margin-bottom: var(--space-6);
}

.newpage-title {
  font-family: var(--font-serif);
  font-size: var(--text-3xl);
  font-weight: var(--weight-bold);
  color: var(--color-wood-dark);
}

.newpage-body {
  ...
}

@media (max-width: 768px) {
  .newpage-page {
    padding: var(--space-4);
  }
}
</style>
```

---

## 7. 状态管理规范

### 7.1 Store 定义模式

所有 Store 使用 Pinia `defineStore` + setup 函数式语法：

```ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSomeStore = defineStore('some', () => {
  // 状态
  const stateA = ref<TypeA>(initialValue)

  // 计算属性
  const derivedB = computed(() => ...)

  // 方法
  function doSomething() { ... }

  // 异步方法
  async function fetchData() {
    try {
      const result = await wsClient.request(WSMsgType.SOME_TYPE, { ... })
      stateA.value = result.data
    } catch (error) {
      console.error('[StoreName] Error:', error)
    }
  }

  // 重置
  function $reset() {
    stateA.value = initialValue
  }

  return { stateA, derivedB, doSomething, fetchData, $reset }
})
```

### 7.2 Store 使用原则

1. **组件内使用**：`const store = useSomeStore()`，直接在模板中 `store.xxx`
2. **禁止跨 Store 直接修改**：Store A 需修改 Store B 的状态时，应调用 Store B 的方法
3. **异步操作**：统一 `try/catch`，错误通过 `console.error('[Store名]')` + `showToast()` 提示
4. **日志前缀**：所有 Store 内的 `console.error/warn/log` 必须带 `[Store名]` 前缀

---

## 8. WebSocket 通信规范

### 8.1 请求模式

```ts
// 请求-响应式（带 seq 匹配）
const result = await wsClient.request(WSMsgType.USER_GET_ME, { })
// result = { success: true, data: { ... } } 或 throw Error
```

### 8.2 推送处理模式

Handler 注册在 `App.vue` 中统一执行，处理器文件按领域拆分：

```ts
// ws/handlers/some.handler.ts
import { messageRouter } from '@/ws/router'
import { WSRespType } from '@/ws/types'

export function registerSomeHandlers() {
  messageRouter.on(WSRespType.SOME_RESULT, (data) => {
    // 处理推送消息
    console.log('[SomeHandler] Received:', data)
  })
}
```

### 8.3 新增消息类型

1. 在 `ws/types.ts` 的 `WSMsgType` / `WSRespType` 中添加常量
2. 在 `ws/types.ts` 中定义对应的 Data 接口类型
3. 创建或更新 `ws/handlers/{领域}.handler.ts`
4. 在 `App.vue` 中调用注册函数

---

## 9. SVG 资源规范

### 9.1 图标命名

所有 UI 图标放在 `public/assets/svg/ui/`，命名格式：`icon-{名称}.svg`

现有图标清单：

| 图标文件 | 用途 |
|---------|------|
| `icon-ai.svg` | AI/人机对战 |
| `icon-back.svg` | 返回 |
| `icon-check.svg` | 确认/勾选 |
| `icon-clock.svg` | 计时/记录 |
| `icon-close.svg` | 关闭弹窗 |
| `icon-exit.svg` | 退出 |
| `icon-flag.svg` | 认输/败北 |
| `icon-fullscreen.svg` | 全屏 |
| `icon-import.svg` | 导入 |
| `icon-next.svg` | 下一步 |
| `icon-pause.svg` | 暂停 |
| `icon-play.svg` | 开始/播放 |
| `icon-plus.svg` | 新增/创建 |
| `icon-prev.svg` | 上一步 |
| `icon-refresh.svg` | 重来/刷新 |
| `icon-settings.svg` | 设置 |
| `icon-sound-on.svg` | 音效开 |
| `icon-sound-off.svg` | 音效关 |
| `icon-star.svg` | 星/段位 |
| `icon-sword.svg` | 对战 |
| `icon-trophy.svg` | 胜利 |
| `icon-undo.svg` | 撤销/求和 |
| `icon-user.svg` | 用户头像底图 |
| `logo.svg` | Logo 图标 |
| `text-logo.svg` | Logo 文字横幅 |

### 9.2 图标使用规范

```html
<!-- 按钮内图标（小） -->
<img :src="baseUrl + 'assets/svg/ui/icon-xxx.svg'" alt="" class="btn-icon-xs" />

<!-- 标题图标 -->
<img :src="baseUrl + 'assets/svg/ui/icon-xxx.svg'" alt="" class="title-icon" />

<!-- 头像底图 -->
<img :src="baseUrl + 'assets/svg/ui/icon-user.svg'" alt="" class="avatar-icon" />
```

对应 CSS：
```css
.btn-icon-xs { width: 16px; height: 16px; flex-shrink: 0; }
.btn-icon-sm { width: 18px; height: 18px; vertical-align: middle; }
.title-icon  { width: 20px; height: 20px; flex-shrink: 0; }
.avatar-icon { width: 32px; height: 32px; opacity: 0.15; position: absolute; }
```

### 9.3 新增图标要求

- 尺寸：SVG `viewBox` 建议 `24×24` 或 `32×32`
- 风格：线性图标（stroke），颜色用 `currentColor` 或 `#92400E`（木色）
- 格式：纯 SVG，不含多余命名空间或外部引用
- 放置：`public/assets/svg/ui/icon-{名称}.svg`

---

## 10. 路由规范

### 10.1 路由定义

```ts
const routes: RouteRecordRaw[] = [
  {
    path: '/newpage',
    name: 'NewPage',
    component: () => import('@/pages/NewPage.vue'),  // 懒加载
    meta: { requiresAuth: true, title: '页面标题' },
  },
]
```

### 10.2 路由守卫

`router/index.ts` 中 `beforeEach` 已处理：
- 需要 `requiresAuth` 但 WS 未连接 → 重定向到 Splash
- 已认证用户访问登录页 → 重定向到 Lobby

新路由默认 `requiresAuth: true`，公开页面设 `requiresAuth: false`。

### 10.3 页面间导航

```ts
// 正常跳转
router.push('/lobby')
router.push(`/game/${roomId}`)

// 替换（不可回退）
router.replace('/lobby')

// 返回
router.back()
```

---

## 11. 类型定义规范

### 11.1 类型文件归属

| 文件 | 内容 |
|------|------|
| `types/chess.ts` | 棋子编码、棋盘常量、走法类型、Position/Move 等 |
| `types/api.ts` | API 交互类型 |
| `ws/types.ts` | WS 协议类型（消息结构、消息类型常量、数据接口） |

### 11.2 类型定义规范

- 使用 `const` 对象 + `as const` 定义枚举常量（如 `Piece`、`WSMsgType`）
- 使用 `interface` 定义数据结构
- 使用 `typeof Obj[keyof typeof Obj]` 提取类型
- 禁止使用 `enum`（与 Vue/Vite 构建优化不兼容）
- Store 导出的类型用 `export interface`

```ts
// ✅ 正确
export const Color = { Red: 0, Black: 1 } as const
export type ColorType = typeof Color[keyof typeof Color]

// ❌ 禁止
export enum Color { Red = 0, Black = 1 }
```

---

## 12. 错误处理与日志规范

### 12.1 错误处理层次

| 场景 | 处理方式 |
|------|---------|
| Store 异步操作失败 | `try/catch` → `console.error('[Store名] xxx:', error)` + `showToast()` |
| WS 请求失败 | `wsClient.request()` 自带 throw → Store catch |
| 路由守卫拦截 | `router.replace()` 跳转 |
| 表单验证 | 函数返回 `boolean` + errors reactive |
| 走棋错误 | `onMoveError` callback → `showToast()` |

### 12.2 日志规范

- Store 日志：`console.error('[Auth] Login failed:', error)`
- WS 日志：`console.warn('[WS Router] Unhandled message type:', type)`
- 组件日志：`console.error('[Game] Move error:', msg)`
- **禁止**在生产代码中使用 `console.log()`，仅用 `console.error()` / `console.warn()`
- **禁止**将敏感信息（token、密码）写入日志

---

## 13. 音效规范

### 13.1 SoundManager 使用

```ts
import { getSoundManager, type SoundKey } from '@/utils/sound'

const sound = getSoundManager()

// 初始化（App.vue onMounted 中执行）
await sound.init()

// 播放音效
sound.play('move')       // 落子声
sound.play('capture')    // 吃子声
sound.play('check')      // 将军声

// 开关
sound.toggleSound(true / false)
sound.soundEnabled  // ref<boolean>
```

### 13.2 新增音效

1. WAV 文件放入 `public/assets/wav/`
2. 在 `utils/sound.ts` 的 SoundConfig 中注册
3. SoundKey 类型自动扩展

---

## 14. 构建与部署

### 14.1 Vite 配置要点

```ts
// vite.config.ts
export default defineConfig({
  base: '/xiangqi/',  // 部署子路径
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/xiangqi/ws': {
        target: 'ws://localhost:8765',
        ws: true,
        rewrite: (path) => path.replace(/^\/xiangqi\/ws/, '/ws'),
      },
    },
  },
})
```

### 14.2 关键点

- 所有 `public/assets/` 资源路径必须通过 `baseUrl` (`import.meta.env.BASE_URL`) 拼接
- 路径别名 `@` → `src/`
- 开发时 WS 代理 `/xiangqi/ws` → `ws://localhost:8765/ws`
- 构建产物部署到 `/xiangqi/` 子路径下

---

## 15. Checklist：新功能开发检查清单

在提交新功能代码前，逐项检查：

### 代码结构

- [ ] 文件放在正确的目录（pages / components/{领域} / stores / ws / types / styles）
- [ ] 文件命名符合规范（PascalCase.vue / camelCase.ts / kebab-case.css）
- [ ] `<script setup>` 结构顺序符合 §3.1
- [ ] `baseUrl` 已声明（如有 SVG 引用）

### 样式

- [ ] 使用 CSS 变量而非硬编码值
- [ ] scoped 样式，不污染全局
- [ ] 页面 CSS 已在 `main.css` 注册
- [ ] 768px 移动端断点有适配
- [ ] 没有使用 emoji 作为 UI 图标
- [ ] 没有重写全局公共组件样式（`.btn` `.toggle` `.lobby-overlay` 等）

### 类型与交互

- [ ] Props/Emits 使用 TypeScript 泛型语法
- [ ] 常量用 `as const`，不用 `enum`
- [ ] Toast/Confirm 使用 `showToast()` / `showConfirm()`，不引入第三方库
- [ ] WS 新类型已在 `types.ts` 注册
- [ ] WS handler 已注册并在 `App.vue` 中调用

### 质量

- [ ] JSDoc 注释：组件顶部、关键方法
- [ ] 错误处理：`try/catch` + `console.error('[前缀]')` + `showToast()`
- [ ] 无 `console.log()`，无 TODO，无省略号
- [ ] 无硬编码密钥或敏感信息
- [ ] 无安全漏洞（XSS / SQL注入等）
