import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/lobby',
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

// 路由守卫 — 基于 WS 认证状态
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && authStore.authState === 'unauthenticated') {
    // 需要认证但未认证，跳转到登录页
    return { name: 'Login', query: { redirect: to.fullPath } }
  } else if (!requiresAuth && authStore.authState !== 'unauthenticated' && authStore.authState !== 'restoring') {
    // 已认证访问登录/注册页，跳转到大厅
    return { name: 'Lobby' }
  } else {
    // restoring 状态：不重定向，让页面显示 loading 等待凭证恢复结果
    return
  }
})

export default router
