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

/** Logged-in renew / redeem activation code */
export function activate(inviteCode) {
  return api.post('/auth/activate', { invite_code: String(inviteCode || '').trim() })
}

/** Self-service account deletion (non-admin). Body: { password } */
export function deleteAccount(password) {
  return api.post('/auth/delete-account', { password: String(password || '') })
}
