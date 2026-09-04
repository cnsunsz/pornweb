<template>
  <div class="admin">
    <h2>{{ t('lib.title') }}</h2>

    <!-- Sticky compact progress strip while any library is scanning -->
    <div v-if="stickyScan" class="scan-sticky">
      <div class="scan-sticky-head">
        <span class="scan-sticky-title">{{ stickyScan.name || t('lib.scanning') }}</span>
        <span class="scan-sticky-pct" v-if="scanPercent(stickyScan.status) != null">{{ scanPercent(stickyScan.status) }}%</span>
      </div>
      <el-progress
        :percentage="scanPercent(stickyScan.status) ?? 0"
        :indeterminate="scanPercent(stickyScan.status) == null"
        :stroke-width="8"
        :show-text="false"
        striped
        striped-flow
        status="success"
      />
      <div class="scan-meta">
        <span v-if="stickyScan.status.phase || stickyScan.status.message">{{ stickyScan.status.phase || stickyScan.status.message }}</span>
        <span v-if="stickyScan.status.current" class="scan-current">{{ stickyScan.status.current }}</span>
        <span class="scan-counts">{{ formatCounts(stickyScan.status) }}</span>
      </div>
    </div>

    <el-card>
      <template #header><span class="ch">{{ t('lib.add') }}</span></template>
      <div class="add-form">
        <el-input v-model="libPath" :placeholder="t('lib.pathPh')" size="large" clearable>
          <template #prepend>{{ t('lib.path') }}</template>
        </el-input>
        <el-input v-model="libName" :placeholder="t('lib.namePh')" size="large" style="width:180px" />
        <el-select v-model="libType" size="large" style="width:100px">
          <el-option :label="t('home.movie')" value="movie" /><el-option :label="t('home.show')" value="tvshow" /><el-option :label="t('lib.mixed')" value="mixed" />
        </el-select>
        <el-button type="primary" size="large" :loading="scanning" :disabled="scanning" @click="doScan">{{ t('lib.scan') }}</el-button>
      </div>
      <el-alert v-if="scanResult && !isRunningStatus(scanResult)" :title="scanText" :type="scanAlertType" show-icon style="margin-top:12px" @close="scanResult=null" />
    </el-card>

    <el-card v-if="libs.length">
      <template #header><span class="ch">{{ t('lib.libraries') }}</span></template>
      <div class="lib-list">
        <div v-for="lib in libs" :key="lib.id || lib.path" class="lib-item" :class="{ scanning: isLibScanning(lib) }">
          <div class="lib-main">
            <div class="lib-info">
              <svg viewBox="0 0 24 24" width="20" height="20"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" fill="var(--accent)"/></svg>
              <div class="lib-text">
                <div class="lib-name">{{ lib.name }}</div>
                <div class="lib-path">{{ lib.path }} · {{ lib.count || 0 }} {{ t('lib.itemsShort') }}{{ isLibScanning(lib) ? ' · ' + t('lib.scanning') : '' }}</div>
              </div>
            </div>
            <div class="lib-acts">
              <el-tag :type="lib.type==='movie'?'primary':'warning'" size="small">{{ lib.type==='movie'?t('home.movie'):lib.type==='tvshow'?t('home.show'):t('lib.mixed') }}</el-tag>
              <el-button size="small" @click="renameLib(lib)" :disabled="isLibScanning(lib)">{{ t('lib.rename') }}</el-button>
              <el-button size="small" @click="rescan(lib)" :loading="!!lib._sc || isLibScanning(lib)" :disabled="isLibScanning(lib)">{{ t('lib.rescan') }}</el-button>
              <el-button size="small" type="danger" text @click="removeLib(lib)" :disabled="isLibScanning(lib)">{{ t('lib.remove') }}</el-button>
            </div>
          </div>

          <!-- Per-library Emby/Jellyfin-style scan progress -->
          <div v-if="statusFor(lib)" class="lib-scan">
            <div class="lib-scan-row">
              <span class="lib-scan-phase">{{ statusFor(lib).phase || statusFor(lib).message || t('lib.scanning') }}</span>
              <span v-if="scanPercent(statusFor(lib)) != null" class="lib-scan-pct">{{ scanPercent(statusFor(lib)) }}%</span>
            </div>
            <el-progress
              :percentage="scanPercent(statusFor(lib)) ?? (isRunningStatus(statusFor(lib)) ? 100 : 0)"
              :indeterminate="isRunningStatus(statusFor(lib)) && scanPercent(statusFor(lib)) == null"
              :stroke-width="10"
              :show-text="false"
              striped
              :striped-flow="isRunningStatus(statusFor(lib))"
              :status="statusFor(lib).status === 'error' ? 'exception' : (statusFor(lib).status === 'done' ? 'success' : undefined)"
            />
            <div class="scan-meta">
              <span v-if="statusFor(lib).current" class="scan-current">{{ statusFor(lib).current }}</span>
              <span class="scan-counts">{{ formatCounts(statusFor(lib)) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card>
      <template #header><span class="ch">{{ t('lib.list') }} <el-tag type="info" size="small" style="margin-left:8px">{{ t('lib.total', { n: store.total }) }}</el-tag></span></template>
      <el-table :data="store.items" stripe v-loading="store.loading" size="small">
        <el-table-column :label="t('lib.titleCol')" min-width="180" show-overflow-tooltip>
          <template #default="{row}">
            <div style="display:flex;align-items:center;gap:8px">
              <img v-if="row.id" :src="posterUrl(row.id)" style="width:28px;height:42px;object-fit:cover;border-radius:3px" @error="$event.target.style.display='none'" />
              <span>{{ row.title }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('lib.type')" width="70">
          <template #default="{row}"><el-tag :type="row.category==='tvshow'?'warning':'primary'" size="small">{{ row.category==='tvshow'?t('home.show'):t('home.movie') }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="year" :label="t('lib.year')" width="65" />
        <el-table-column :label="t('lib.rating')" width="60">
          <template #default="{row}"><span v-if="row.rating" style="color:#f0c040">{{ row.rating.toFixed(1) }}</span><span v-else style="color:#444">-</span></template>
        </el-table-column>
        <el-table-column :label="t('lib.size')" width="80">
          <template #default="{row}">{{ fmtSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column :label="t('lib.actions')" width="60" fixed="right">
          <template #default="{row}"><el-button type="danger" size="small" text @click="del(row)">{{ t('lib.delete') }}</el-button></template>
        </el-table-column>
      </el-table>
      <div v-if="store.total>0" style="display:flex;justify-content:center;margin-top:16px">
        <el-pagination :current-page="pg" :page-size="store.pageSize" :total="store.total" layout="total,prev,pager,next" @current-change="p=>{pg=p;store.page=p;store.fetchList()}" background small />
      </div>
    </el-card>
  </div>
</template>
<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { scanMedia, deleteMedia, getPosterUrl, getLibraries, createLibrary, deleteLibrary, scanLibrary, updateLibrary, getScanStatus } from '@/api/media'
import { ElMessage, ElMessageBox } from 'element-plus'
const { t } = useI18n()
const store = useMediaStore()
const libs = ref([])
const libPath = ref(''); const libName = ref(''); const libType = ref('movie')
const scanning = ref(false); const scanResult = ref(null); const pg = ref(1)
/** @type {import('vue').Reactive<Record<string|number, object>>} */
const scanByLib = reactive({})
const polling = new Set()

const scanText = computed(() => {
  if (scanResult.value?.error) return scanResult.value.error
  if (scanResult.value?.message) return scanResult.value.message
  return t('lib.scanDone', { added: scanResult.value?.added||0, updated: scanResult.value?.updated||0, removed: scanResult.value?.removed||0 })
})
const scanAlertType = computed(() => {
  if (scanResult.value?.error || scanResult.value?.status === 'error') return 'error'
  if (scanResult.value?.status === 'running') return 'info'
  return 'success'
})

const stickyScan = computed(() => {
  for (const lib of libs.value || []) {
    const st = statusFor(lib)
    if (st && isRunningStatus(st)) return { name: lib.name, status: st }
  }
  for (const [id, st] of Object.entries(scanByLib)) {
    if (isRunningStatus(st)) {
      const lib = (libs.value || []).find(l => String(l.id) === String(id))
      return { name: lib?.name || t('lib.scanning'), status: st }
    }
  }
  return null
})

function posterUrl(id) { return getPosterUrl(id) }

function isRunningStatus(st) {
  return st && st.status === 'running'
}

function statusFor(lib) {
  if (!lib) return null
  const key = lib.id != null ? lib.id : lib.path
  return scanByLib[key] || null
}

function isLibScanning(lib) {
  if (lib?.scan_status === 'running') return true
  const st = statusFor(lib)
  return isRunningStatus(st) || !!lib?._sc
}

/** Determinate % from processed/found (or current numeric), else null → indeterminate. */
function scanPercent(st) {
  if (!st) return null
  const found = Number(st.found) || 0
  const processed = Number(st.processed) || 0
  if (found > 0) return Math.min(100, Math.round((processed / found) * 100))
  if (st.status === 'done') return 100
  return null
}

function formatCounts(st) {
  if (!st) return ''
  const parts = []
  if (st.found != null) parts.push(t('lib.scanFound', { n: st.found }))
  if (st.processed != null) parts.push(t('lib.scanProcessed', { n: st.processed }))
  if (st.added != null) parts.push(t('lib.scanAdded', { n: st.added }))
  if (st.updated != null) parts.push(t('lib.scanUpdated', { n: st.updated }))
  if (st.removed != null) parts.push(t('lib.scanRemoved', { n: st.removed }))
  return parts.join(' · ')
}

async function loadLibs() {
  try {
    const res = await getLibraries()
    libs.value = res.data || []
  } catch (e) {
    console.error(e)
  }
}

async function migrateLocal() {
  const saved = JSON.parse(localStorage.getItem('mv_libraries') || '[]')
  if (!saved.length || libs.value.length) return
  for (const s of saved) {
    try {
      await createLibrary({ name: s.name || s.path, path: s.path, type: s.type || 'movie' })
    } catch {}
  }
  localStorage.removeItem('mv_libraries')
  await loadLibs()
}

function setScanStatus(libId, data) {
  if (libId == null) return
  scanByLib[libId] = data
  scanResult.value = data
}

async function pollScan(libId, after) {
  const key = libId != null ? libId : '_tmp'
  if (polling.has(key)) {
    if (after) after()
    return
  }
  polling.add(key)
  setScanStatus(key, { status: 'running', added: 0, updated: 0, removed: 0, found: 0, processed: 0, message: t('lib.scanning') })
  try {
    for (let i = 0; i < 3600; i++) {
      try {
        const res = libId ? await getScanStatus(libId) : null
        const data = res && res.data
        if (data) setScanStatus(key, data)
        await loadLibs()
        await store.fetchList()
        const st = data && data.status
        if (st === 'done' || st === 'error' || st === 'idle') {
          if (st === 'error') ElMessage.error((data && (data.error || data.message)) || t('lib.scanFail'))
          else if (st === 'done') ElMessage.success(t('lib.scanOk'))
          break
        }
      } catch {}
      await new Promise(r => setTimeout(r, 1500))
    }
  } finally {
    polling.delete(key)
    if (after) after()
  }
}

async function doScan() {
  if (!libPath.value.trim()) { ElMessage.warning(t('lib.pathReq')); return }
  if (!libName.value.trim()) { ElMessage.warning(t('lib.nameReq')); return }
  scanning.value = true; scanResult.value = null
  try {
    const created = await createLibrary({ name: libName.value.trim(), path: libPath.value.trim(), type: libType.value })
    libPath.value=''; libName.value=''
    await scanLibrary(created.data.id)
    await pollScan(created.data.id, () => { scanning.value = false })
  } catch(e) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string' && detail.includes('已添加')) {
      try {
        const r = await scanMedia(libPath.value.trim())
        const jobLib = r.data && r.data.library_id
        await pollScan(jobLib, () => { scanning.value = false })
      } catch (e2) {
        scanResult.value = { error: e2.response?.data?.detail || t('lib.scanFail') }
        scanning.value = false
      }
    } else {
      scanResult.value = { error: detail || t('lib.scanFail') }
      scanning.value = false
    }
  }
}
async function rescan(lib) {
  if (isLibScanning(lib)) return
  lib._sc = true
  try {
    if (lib.id) await scanLibrary(lib.id)
    else await scanMedia(lib.path)
    await pollScan(lib.id || lib.path, () => { lib._sc = false })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('lib.scanFail'))
    lib._sc = false
  }
}
async function removeLib(lib) {
  await ElMessageBox.confirm(t('lib.confirmRemove', { name: lib.name }), t('lib.confirm'))
  try {
    if (lib.id) await deleteLibrary(lib.id)
  } catch {}
  await loadLibs(); store.fetchList(); ElMessage.success(t('lib.removed'))
}
async function del(row) {
  try {
    await ElMessageBox.confirm(t('lib.confirmDel', { name: row.title }), t('lib.confirm'), { type: 'warning' })
    await deleteMedia(row.id)
    ElMessage.success(t('lib.deleted'))
    store.fetchList()
  } catch {}
}
async function renameLib(lib) {
  if (!lib.id) { ElMessage.warning(t('lib.needAdd')); return }
  try {
    const { value } = await ElMessageBox.prompt(t('lib.newName'), t('lib.rename'), { inputValue: lib.name, confirmButtonText: t('dash.save') })
    const name = (value || '').trim()
    if (!name) return
    await updateLibrary(lib.id, { name })
    ElMessage.success(t('lib.renamed'))
    await loadLibs()
  } catch {}
}
function fmtSize(b) {
  if (!b) return '-'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, s = b
  while (s >= 1024 && i < u.length - 1) { s /= 1024; i++ }
  return s.toFixed(1) + ' ' + u[i]
}
onMounted(async () => {
  store.pageSize = 50
  await store.fetchList()
  await loadLibs()
  await migrateLocal()
  const run = (libs.value || []).find(l => l.scan_status === 'running')
  if (run) {
    scanning.value = true
    pollScan(run.id, () => { scanning.value = false })
  }
})
</script>
<style scoped>
.admin { display:flex; flex-direction:column; gap:20px; max-width:1100px; }
.admin h2 { font-size:22px; }
.ch { font-weight:600; }
.add-form { display:flex; gap:10px; flex-wrap:wrap; }
.add-form .el-input { flex:1; min-width:200px; }
.lib-list { display:flex; flex-direction:column; gap:10px; }
.lib-item {
  display:flex; flex-direction:column; gap:10px;
  padding:12px 16px; background:var(--bg); border-radius:8px; border:1px solid var(--border);
}
.lib-item.scanning { border-color: rgba(0,164,220,.45); box-shadow: 0 0 0 1px rgba(0,164,220,.12); }
.lib-main { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.lib-info { display:flex; align-items:center; gap:12px; min-width:0; }
.lib-text { min-width:0; }
.lib-name { font-weight:600; font-size:14px; }
.lib-path { font-size:12px; color:var(--text-muted); margin-top:2px; word-break:break-all; }
.lib-acts { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.lib-scan { padding-top:2px; }
.lib-scan-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; gap:8px; }
.lib-scan-phase { font-size:12px; color:var(--text-dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lib-scan-pct { font-size:12px; font-weight:600; color:var(--accent); font-variant-numeric:tabular-nums; }
.scan-meta {
  display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:6px;
  font-size:11px; color:var(--text-muted);
}
.scan-current { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.scan-counts { font-variant-numeric:tabular-nums; }

.scan-sticky {
  position: sticky; top: 0; z-index: 20;
  padding: 12px 14px; border-radius: 8px;
  background: rgba(20,20,20,.92); border: 1px solid rgba(0,164,220,.35);
  backdrop-filter: blur(8px);
}
.scan-sticky-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.scan-sticky-title { font-size:13px; font-weight:600; color:var(--accent); }
.scan-sticky-pct { font-size:13px; font-weight:700; color:var(--accent); font-variant-numeric:tabular-nums; }
</style>
