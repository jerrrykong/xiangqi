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
    path: '/room/:id',
    name: 'GameRoom',
    component: () => import('@/pages/GameRoom.vue'),
    meta: { requiresAuth: true, title: '游戏房间' },
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

// 路由守卫
router.beforeEach((to, from) => {
  const authStore = useAuthStore()
  const requiresAuth = to.meta.requiresAuth !== false

  // 初始化认证状态
  if (!authStore.user && authStore.token) {
    authStore.init()
  }

  if (requiresAuth && !authStore.isAuthenticated) {
    // 需要登录，跳转到登录页
    return { name: 'Login', query: { redirect: to.fullPath } }
  } else if ((to.name === 'Login' || to.name === 'Register') && authStore.isAuthenticated) {
    // 已登录，跳转到大厅
    return { name: 'Lobby' }
  } else {
    // next()
    return
  }
})

export default router
