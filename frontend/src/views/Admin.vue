<template>
  <div class="admin">
    <h2>{{ t('lib.title') }}</h2>

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
        <el-button type="primary" size="large" :loading="scanning" @click="doScan">{{ t('lib.scan') }}</el-button>
      </div>
      <el-alert v-if="scanResult" :title="scanText" :type="scanAlertType" show-icon style="margin-top:12px" @close="scanResult=null" />
    </el-card>

    <el-card v-if="libs.length">
      <template #header><span class="ch">{{ t('lib.libraries') }}</span></template>
      <div class="lib-list">
        <div v-for="lib in libs" :key="lib.id || lib.path" class="lib-item">
          <div class="lib-info">
            <svg viewBox="0 0 24 24" width="20" height="20"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" fill="var(--accent)"/></svg>
            <div>
              <div class="lib-name">{{ lib.name }}</div>
              <div class="lib-path">{{ lib.path }} · {{ lib.count || 0 }} 项{{ lib.scan_status === 'running' ? ' · 扫描中' : '' }}</div>
            </div>
          </div>
          <div class="lib-acts">
            <el-tag :type="lib.type==='movie'?'primary':'warning'" size="small">{{ lib.type==='movie'?t('home.movie'):lib.type==='tvshow'?t('home.show'):t('lib.mixed') }}</el-tag>
            <el-button size="small" @click="renameLib(lib)">{{ t('lib.rename') }}</el-button>
            <el-button size="small" @click="rescan(lib)" :loading="lib._sc">{{ t('lib.rescan') }}</el-button>
            <el-button size="small" type="danger" text @click="removeLib(lib)">{{ t('lib.remove') }}</el-button>
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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { scanMedia, deleteMedia, getPosterUrl, getLibraries, createLibrary, deleteLibrary, scanLibrary, updateLibrary, getScanStatus } from '@/api/media'
import { ElMessage, ElMessageBox } from 'element-plus'
const { t } = useI18n()
const store = useMediaStore()
const libs = ref([])
const libPath = ref(''); const libName = ref(''); const libType = ref('movie')
const scanning = ref(false); const scanResult = ref(null); const pg = ref(1)
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
function posterUrl(id) { return getPosterUrl(id) }

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

async function pollScan(libId, after) {
  scanResult.value = { status: 'running', added: 0, updated: 0, removed: 0, found: 0, message: '扫描中…' }
  for (let i = 0; i < 3600; i++) {
    try {
      const res = libId ? await getScanStatus(libId) : null
      const data = res && res.data
      if (data) scanResult.value = data
      await loadLibs()
      await store.fetchList()
      const st = data && data.status
      if (st === 'done' || st === 'error' || st === 'idle') {
        if (st === 'error') ElMessage.error((data && (data.error || data.message)) || t('lib.scanFail'))
        else ElMessage.success(t('lib.scanOk'))
        break
      }
    } catch {}
    await new Promise(r => setTimeout(r, 1500))
  }
  if (after) after()
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
  lib._sc = true
  try {
    if (lib.id) await scanLibrary(lib.id)
    else await scanMedia(lib.path)
    await pollScan(lib.id, () => { lib._sc = false })
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
.lib-item { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; background:var(--bg); border-radius:8px; border:1px solid var(--border); }
.lib-info { display:flex; align-items:center; gap:12px; }
.lib-name { font-weight:600; font-size:14px; }
.lib-path { font-size:12px; color:var(--text-muted); margin-top:2px; }
.lib-acts { display:flex; align-items:center; gap:8px; }
</style>
