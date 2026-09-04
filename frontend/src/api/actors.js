import api from './index'

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
