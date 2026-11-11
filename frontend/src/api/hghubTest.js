import api from './index'

export function hghubLines() {
  return api.get('/hghub-test/lines')
}

export function hghubFeed(params) {
  return api.get('/hghub-test/feed', { params })
}

export function hghubSearch(params) {
  return api.get('/hghub-test/search', { params })
}

export function hghubVideo(id, params) {
  return api.get(`/hghub-test/video/${id}`, { params })
}

export function hghubEdge(data) {
  return api.post('/hghub-test/edge', data)
}
