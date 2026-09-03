import api from './index'

export function register(username, email, password) {
  return api.post('/auth/register', { username, email, password })
}

export function login(username, password) {
  return api.post('/auth/login', { username, password })
}

export function getMe() {
  return api.get('/auth/me')
}
