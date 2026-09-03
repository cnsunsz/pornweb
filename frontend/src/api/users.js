import api from './index'

export function getUsers() {
  return api.get('/users/')
}

export function createUser(data) {
  return api.post('/users/', data)
}

export function updateUser(userId, data) {
  return api.put(`/users/${userId}`, data)
}

export function deleteUser(userId) {
  return api.delete(`/users/${userId}`)
}

export function changePassword(data) {
  return api.put('/users/me/password', data)
}
