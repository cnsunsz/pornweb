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

/** Admin: renew/extend membership without invite code */
export function renewUser(userId, data) {
  return api.post(`/admin/users/${userId}/renew`, data)
}

export function getUserLibraries(userId) {
  return api.get(`/admin/users/${userId}/libraries`)
}

export function putUserLibraries(userId, libraryIds) {
  return api.put(`/admin/users/${userId}/libraries`, { library_ids: libraryIds })
}
