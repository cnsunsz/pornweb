<template>
  <div class="page">
    <div class="head">
      <div>
        <h1>黄果接口测试</h1>
        <p class="note">只给管理员做连通性测试，结果不会写入 PornWeb 媒体库。</p>
      </div>
      <div class="controls">
        <el-select v-model="base" size="small" style="width: 220px">
          <el-option
            v-for="line in lines"
            :key="line.url"
            :label="`${line.name} · ${line.url.replace('https://', '')}`"
            :value="line.url"
          />
        </el-select>
        <el-input
          v-model="q"
          size="small"
          clearable
          placeholder="搜索"
          style="width: 180px"
          @keyup.enter="doSearch"
        />
        <el-button size="small" type="primary" :loading="loading" @click="doFeed">拉首页</el-button>
        <el-button size="small" :loading="loading" :disabled="!q.trim()" @click="doSearch">搜索</el-button>
      </div>
    </div>

    <p v-if="meta" class="meta">{{ meta }}</p>
    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" style="margin-bottom: 16px" />

    <div v-if="items.length" class="grid">
      <button v-for="item in items" :key="item.id" class="card" @click="openDetail(item)">
        <img v-if="item.cover" :src="item.cover" :alt="item.title" loading="lazy" referrerpolicy="no-referrer" />
        <div v-else class="ph" />
        <div class="cap">
          <strong>{{ item.title }}</strong>
          <span>ID {{ item.id }}</span>
        </div>
      </button>
    </div>

    <pre v-if="detail" class="json">{{ detail }}</pre>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { hghubFeed, hghubLines, hghubSearch, hghubVideo } from '@/api/hghubTest'

const lines = ref([
  { name: '固定线路 1', url: 'https://huangguoai.com' },
  { name: '固定线路 2', url: 'https://huangguoai.ai' },
])
const base = ref('https://huangguoai.com')
const q = ref('')
const loading = ref(false)
const error = ref('')
const meta = ref('')
const items = ref([])
const detail = ref('')

function params() {
  return { base: base.value }
}

function applyResult(res, fallbackItems) {
  const body = res.data || {}
  const data = body.data
  const list = data?.items || fallbackItems || []
  items.value = Array.isArray(list) ? list : []
  const total = data?.pagination?.total
  const ms = body.elapsed_ms
  meta.value = [
    body.base,
    body.path,
    ms != null ? `${ms} ms` : '',
    total != null ? `共 ${total} 条` : `${items.value.length} 条`,
  ].filter(Boolean).join(' · ')
  detail.value = JSON.stringify(data, null, 2)
}

async function run(fn) {
  loading.value = true
  error.value = ''
  meta.value = ''
  try {
    applyResult(await fn())
  } catch (e) {
    items.value = []
    detail.value = ''
    error.value = e.response?.data?.detail || e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function doFeed() {
  return run(() => hghubFeed({ page: 1, size: 12, ...params() }))
}

function doSearch() {
  const query = q.value.trim()
  if (!query) return
  return run(() => hghubSearch({ q: query, page: 1, size: 12, ...params() }))
}

async function openDetail(item) {
  loading.value = true
  error.value = ''
  try {
    const res = await hghubVideo(item.id, params())
    const body = res.data || {}
    meta.value = [body.base, body.path, body.elapsed_ms != null ? `${body.elapsed_ms} ms` : ''].filter(Boolean).join(' · ')
    detail.value = JSON.stringify(body.data, null, 2)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '详情失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await hghubLines()
    const data = res.data || {}
    if (Array.isArray(data.fixed) && data.fixed.length) lines.value = data.fixed
    if (data.default) base.value = data.default
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '无法读取线路'
  }
})
</script>

<style scoped>
.page { color: var(--text, #eee); }
.head { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
h1 { margin: 0 0 6px; font-size: 20px; }
.note, .meta { margin: 0; color: var(--muted, #999); font-size: 13px; }
.meta { margin: 0 0 14px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.card { text-align: left; background: var(--card, #1a1a1a); border: 0; border-radius: 8px; overflow: hidden; color: inherit; cursor: pointer; padding: 0; }
.card img, .ph { width: 100%; aspect-ratio: 3/4; object-fit: cover; background: #222; display: block; }
.cap { padding: 8px; display: flex; flex-direction: column; gap: 2px; }
.cap strong { font-size: 13px; line-height: 1.3; }
.cap span { font-size: 11px; color: #888; }
.json { margin-top: 18px; padding: 12px; background: #111; border-radius: 8px; overflow: auto; font-size: 12px; line-height: 1.45; max-height: 480px; }
</style>
