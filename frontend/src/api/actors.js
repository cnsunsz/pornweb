import api from './index'

function tokenQ() {
  const token = localStorage.getItem('token') || ''
  return encodeURIComponent(token)
}

/** 演员列表；可选 search 过滤姓名 */
export function getActors(params) {
  return api.get('/actors', { params })
}

/**
 * 某演员的作品列表（推荐路径 /actors/{name}/media，自动编码 CJK）
 * 响应形状同 getMediaList / MediaListResponse
 */
export function getActorMedia(name, params) {
  return api.get(`/actors/${encodeURIComponent(name)}/media`, { params })
}

/** 备选：查询参数传姓名，避免部分客户端路径编码问题 */
export function getActorMediaByQuery(name, params) {
  return api.get('/actors/by-name', { params: { name, ...params } })
}

/**
 * 在线演员头像（同源代理）。404 表示没有真实头像 — 客户端必须留空，
 * 禁止用作品海报或占位图冒充。
 */
export function getActorPhotoUrl(name) {
  return `/api/actors/photo?name=${encodeURIComponent(name)}&token=${tokenQ()}`
}

/** 管理员：批量补刮演员在线头像 */
export function scrapeActorPhotos(params) {
  return api.post("/actors/scrape-photos", null, { params })
}
