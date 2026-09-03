import api from './index'

function tokenQ() {
  const token = localStorage.getItem('token') || ''
  return encodeURIComponent(token)
}

export function getMediaList(params) {
  return api.get('/media/list', { params })
}

export function getMediaDetail(id) {
  return api.get(`/media/detail/${id}`)
}

export function getStreamUrl(id, part = 0) {
  return `/api/media/stream/${id}?token=${tokenQ()}&part=${part || 0}`
}

export function getPosterUrl(id) {
  return `/api/media/poster/${id}?token=${tokenQ()}`
}

export function getFanartUrl(id) {
  return `/api/media/fanart/${id}?token=${tokenQ()}`
}

export function scanMedia(folder) {
  return api.post('/media/scan', { folder })
}

export function deleteMedia(id) {
  return api.delete(`/media/${id}`)
}

export function deleteLibraryByPath(path) {
  return api.delete('/media/library', { params: { path } })
}

export function getGenres() {
  return api.get('/media/genres')
}

export function getFolders() {
  return api.get('/media/folders')
}

export function getLibraries() {
  return api.get('/libraries/')
}

export function createLibrary(data) {
  return api.post('/libraries/', data)
}

export function deleteLibrary(id) {
  return api.delete(`/libraries/${id}`)
}

export function scanLibrary(id) {
  return api.post(`/libraries/${id}/scan`)
}

export function getScanStatus(id) {
  return api.get(`/libraries/${id}/scan-status`)
}

export function updateLibrary(id, data) {
  return api.put(`/libraries/${id}`, data)
}

export function saveProgress(id, data) {
  return api.put(`/media/progress/${id}`, data)
}

export function getContinue() {
  return api.get('/media/continue')
}
