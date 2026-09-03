import api from './index'

export function getServerSettings() {
  return api.get('/settings/')
}

export function updateServerSettings(data) {
  return api.put('/settings/', data)
}
