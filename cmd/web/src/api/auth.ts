import api from './request'
import type {
  ApiResponse,
  LoginRequest,
  RegisterRequest,
  LoginResponse,
  UserProfile,
} from '@/types/api'

// 注册
export async function register(data: RegisterRequest): Promise<UserProfile> {
  const response = await api.post<ApiResponse<UserProfile>>('/auth/register', data)
  return response.data.data!
}

// 登录
export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await api.post<ApiResponse<LoginResponse>>('/auth/login', data)
  // 保存 token
  if (response.data.data?.token) {
    localStorage.setItem('token', response.data.data.token)
  }
  return response.data.data!
}

// 登出
export function logout(): void {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

// 刷新 Token
export async function refreshToken(): Promise<LoginResponse> {
  const response = await api.post<ApiResponse<LoginResponse>>('/auth/refresh')
  if (response.data.data?.token) {
    localStorage.setItem('token', response.data.data.token)
  }
  return response.data.data!
}

// 检查是否已登录
export function isAuthenticated(): boolean {
  return !!localStorage.getItem('token')
}
