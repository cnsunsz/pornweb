import api from './index'

/** 演员列表；可选 search 过滤姓名 */
export function getActors(params) {
  return api.get('/actors', { params })
}

/** 某演员的作品列表（路径参数，自动编码 CJK） */
export function getActorMedia(name, params) {
  return api.get(`/actors/${encodeURIComponent(name)}`, { params })
}

/** 备选：查询参数传姓名 */
export function getActorMediaByQuery(name, params) {
  return api.get('/actors/by-name', { params: { name, ...params } })
}
