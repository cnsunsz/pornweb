import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMediaList, getMediaDetail, getGenres } from '@/api/media'

export const useMediaStore = defineStore('media', () => {
  const items = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const genres = ref([])
  const currentDetail = ref(null)
  
  async function fetchList(params = {}) {
    loading.value = true
    try {
      const res = await getMediaList({
        page: page.value,
        page_size: pageSize.value,
        ...params
      })
      items.value = res.data.items
      total.value = res.data.total
    } catch {
      items.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }
  
  async function fetchDetail(id) {
    const res = await getMediaDetail(id)
    currentDetail.value = res.data
    return res.data
  }
  
  async function fetchGenres() {
    const res = await getGenres()
    genres.value = res.data
  }
  
  return { items, total, page, pageSize, loading, genres, currentDetail, fetchList, fetchDetail, fetchGenres }
})
