<template>
  <div class="page">
    <div class="head">
      <div>
        <h1>转接</h1>
        <p class="note">来自黄果的内容，只做浏览测试，不会写入本地媒体库。</p>
      </div>
      <div class="controls">
        <el-select v-model="base" size="small" style="width: 220px" @change="doFeed">
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
          placeholder="搜索黄果"
          style="width: 200px"
          @keyup.enter="doSearch"
        />
        <el-button size="small" type="primary" :loading="loading" @click="doFeed">首页</el-button>
        <el-button size="small" :loading="loading" :disabled="!q.trim()" @click="doSearch">搜索</el-button>
      </div>
    </div>

    <p v-if="meta" class="meta">{{ meta }}</p>
    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" style="margin-bottom: 16px" />

    <div v-if="loading && !items.length" class="loading">正在加载…</div>

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

    <div v-if="selected" class="detail">
      <div class="detail-head">
        <h2>{{ selected.title || '详情' }}</h2>
        <el-button size="small" text @click="selected = null; detail = ''">关闭</el-button>
      </div>
      <p v-if="selected.description" class="desc">{{ selected.description }}</p>
      <pre class="json">{{ detail }}</pre>
    </div>
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
const selected = ref(null)

function params() {
  return { base: base.value }
}

function applyResult(res) {
  const body = res.data || {}
  const data = body.data
  const list = data?.items || []
  items.value = Array.isArray(list) ? list : []
  selected.value = null
  detail.value = ''
  const total = data?.pagination?.total
  const ms = body.elapsed_ms
  meta.value = [
    body.base,
    ms != null ? `${ms} ms` : '',
    total != null ? `共 ${total} 条` : `${items.value.length} 条`,
  ].filter(Boolean).join(' · ')
}

async function run(fn) {
  loading.value = true
  error.value = ''
  try {
    applyResult(await fn())
  } catch (e) {
    items.value = []
    selected.value = null
    detail.value = ''
    error.value = e.response?.data?.detail || e.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function doFeed() {
  return run(() => hghubFeed({ page: 1, size: 24, ...params() }))
}

function doSearch() {
  const query = q.value.trim()
  if (!query) return
  return run(() => hghubSearch({ q: query, page: 1, size: 24, ...params() }))
}

async function openDetail(item) {
  loading.value = true
  error.value = ''
  try {
    const res = await hghubVideo(item.id, params())
    const body = res.data || {}
    selected.value = body.data || item
    detail.value = JSON.stringify(body.data, null, 2)
    meta.value = [body.base, body.elapsed_ms != null ? `${body.elapsed_ms} ms` : ''].filter(Boolean).join(' · ')
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
    return
  }
  await doFeed()
})
</script>

<style scoped>
.page { color: var(--text, #eee); }
.head { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
h1 { margin: 0 0 6px; font-size: 20px; }
.note, .meta, .desc { margin: 0; color: var(--muted, #999); font-size: 13px; }
.meta { margin: 0 0 14px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.loading { padding: 40px 0; text-align: center; color: #888; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.card { text-align: left; background: var(--card, #1a1a1a); border: 0; border-radius: 8px; overflow: hidden; color: inherit; cursor: pointer; padding: 0; }
.card img, .ph { width: 100%; aspect-ratio: 3/4; object-fit: cover; background: #222; display: block; }
.cap { padding: 8px; display: flex; flex-direction: column; gap: 2px; }
.cap strong { font-size: 13px; line-height: 1.3; }
.cap span { font-size: 11px; color: #888; }
.detail { margin-top: 22px; padding: 14px; background: #141414; border-radius: 10px; }
.detail-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.detail-head h2 { margin: 0; font-size: 16px; }
.desc { margin: 10px 0 0; white-space: pre-wrap; }
.json { margin-top: 14px; padding: 12px; background: #111; border-radius: 8px; overflow: auto; font-size: 12px; line-height: 1.45; max-height: 420px; }
</style>
