import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { wsClient } from '@/ws/client'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Splash',
    component: () => import('@/pages/Splash.vue'),
    meta: { requiresAuth: false, title: '中国象棋' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/pages/Register.vue'),
    meta: { requiresAuth: false, title: '注册' },
  },
  {
    path: '/lobby',
    name: 'Lobby',
    component: () => import('@/pages/Lobby.vue'),
    meta: { requiresAuth: true, title: '游戏大厅' },
  },
  {
    path: '/rooms',
    name: 'RoomList',
    component: () => import('@/pages/RoomList.vue'),
    meta: { requiresAuth: true, title: '房间列表' },
  },
  {
    path: '/game/:id',
    name: 'Game',
    component: () => import('@/pages/Game.vue'),
    meta: { requiresAuth: true, title: '对局' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 — 基于 WS 连接和认证状态
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const requiresAuth = to.meta.requiresAuth !== false
  const isAuthenticated = authStore.isAuthenticated
  const isWsConnected = wsClient.isConnected

  // 需要认证的页面但 WS 未连接 → 重定向到 Splash 触发重连
  if (requiresAuth && !isWsConnected) {
    // 保存目标路径，Splash 连接成功后可跳回
    return { name: 'Splash', query: { redirect: to.fullPath } }
  }

  if (requiresAuth && !isAuthenticated) {
    // WS 已连接但认证未完成（不应该发生，但防御性处理）
    return { name: 'Splash' }
  }

  if (!requiresAuth && isAuthenticated && to.name !== 'Splash') {
    // 已认证访问登录/注册页，跳转到大厅
    return { name: 'Lobby' }
  }

  // 启动页始终可访问（由组件自身决定行为）
  return
})

export default router
