import { apiFetch, apiPost } from './client';
import type { LoginRequest, LoginResponse, SessionInfo } from '@/types/api';

export async function login(creds: LoginRequest) {
  return apiFetch<LoginResponse>('/api/v2/auth/login', {
    method: 'POST',
    body: creds,
    noAuth: true,
  });
}

export async function logout() {
  return apiPost('/api/v2/auth/logout', {});
}

export async function logoutAll() {
  return apiPost('/api/v2/auth/logout-all', {});
}

export async function getSession() {
  return apiFetch<SessionInfo>('/api/v2/auth/session');
}

export async function changePassword(oldPassword: string, newPassword: string) {
  return apiPost('/api/v2/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  });
}
