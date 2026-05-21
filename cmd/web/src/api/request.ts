import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosError } from 'axios'
import type { ApiResponse } from '@/types/api'

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 添加 token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => {
    return response
  },
  async (error: AxiosError<ApiResponse>) => {
    const originalRequest = error.config
    const requestUrl = originalRequest?.url || ''

    // 如果是登录或注册请求，错误直接返回，不进行认证重试处理
    if (requestUrl.includes('/auth/login') || requestUrl.includes('/auth/register')) {
      return Promise.reject(error)
    }

    // 如果是 401 且不是刷新 token 请求
    if (error.response?.status === 401 && originalRequest) {
      const code = error.response.data?.code

      // Token 过期，尝试刷新
      if (code === 2002) {
        try {
          const refreshResponse = await axios.post('/api/v1/auth/refresh', {}, {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token')}`,
            },
          })

          const newToken = refreshResponse.data.data.token
          localStorage.setItem('token', newToken)

          // 重试原请求
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
          }
          return api(originalRequest)
        } catch (refreshError) {
          // 刷新失败，清除 token 并跳转登录
          localStorage.removeItem('token')
          window.location.href = '/login'
          return Promise.reject(refreshError)
        }
      }

      // 其他认证错误
      localStorage.removeItem('token')
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)

export default api
