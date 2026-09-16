import api from './index'

export function register(username, email, password, inviteCode) {
  const body = { username, email, password }
  if (inviteCode) {
    body.invite_code = String(inviteCode).trim()
  }
  return api.post('/auth/register', body)
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

export function getMe() {
  return api.get('/auth/me')
}
