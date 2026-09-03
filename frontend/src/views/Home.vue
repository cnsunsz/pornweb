<template>
  <div class="home">
    <!-- Continue Watching -->
    <section v-if="continueList.length" class="section">
      <h2 class="section-title">{{ t('home.continue') }}</h2>
      <div class="scroll-row">
        <MediaCard v-for="item in continueList" :key="'c-'+item.id" :item="item" @click="go(item)" />
      </div>
    </section>

    <!-- Libraries -->
    <section v-if="libraries.length" class="section">
      <h2 class="section-title">{{ t('home.libraries') }}</h2>
      <div class="lib-row">
        <div v-for="lib in libraries" :key="lib.path" class="lib-card" @click="openLib(lib)">
          <div class="lib-thumb">
            <img v-if="lib.poster_id" :src="posterUrl(lib.poster_id)" @error="$event.target.style.display='none'" />
            <div class="lib-label">
              <span class="lib-name">{{ lib.name }}</span>
              <span class="lib-count">{{ t('home.items', { n: lib.count }) }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Latest / Filtered -->
    <section class="section">
      <div class="section-top">
        <h2 class="section-title">{{ activeLib ? activeLib.name : t('home.latest') }}</h2>
        <div class="filters">
          <el-input v-model="q" :placeholder="t('home.search')" clearable @keyup.enter="doSearch" @clear="doSearch" size="small" style="width:160px" />
          <el-select v-model="cat" clearable :placeholder="t('home.type')" @change="doSearch" size="small" style="width:100px">
            <el-option :label="t('home.movie')" value="movie" /><el-option :label="t('home.show')" value="tvshow" />
          </el-select>
          <el-select v-model="ord" @change="doSearch" size="small" style="width:100px">
            <el-option :label="t('home.newest')" value="newest" /><el-option :label="t('home.rating')" value="rating" /><el-option :label="t('home.year')" value="year" />
          </el-select>
          <el-button v-if="activeLib" text size="small" @click="clearLib">{{ t('home.backAll') }}</el-button>
        </div>
      </div>

      <div v-if="mediaStore.items.length" class="grid">
        <MediaCard v-for="item in mediaStore.items" :key="item.id" :item="item" @click="go(item)" />
      </div>
      <div v-else-if="!mediaStore.loading" class="empty">
        <svg viewBox="0 0 24 24" width="56" height="56"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg>
        <p>{{ t('home.empty') }}</p>
        <el-button type="primary" @click="$router.push('/settings?tab=libraries')" style="margin-top:12px">{{ t('home.addLib') }}</el-button>
      </div>
      <div v-if="mediaStore.loading" style="display:flex;justify-content:center;padding:30px;color:var(--accent)">
        <el-icon :size="24" class="is-loading"><Loading /></el-icon>
      </div>

      <div v-if="mediaStore.total > mediaStore.pageSize" class="pager">
        <el-pagination :current-page="currentPage" :page-size="mediaStore.pageSize" :total="mediaStore.total"
          layout="prev, pager, next" @current-change="onPage" background small />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { getFolders, getPosterUrl, getContinue } from '@/api/media'
import { Loading } from '@element-plus/icons-vue'
import MediaCard from '@/components/MediaCard.vue'

const { t } = useI18n()
const router = useRouter()
const mediaStore = useMediaStore()

const q = ref('')
const cat = ref('')
const ord = ref('newest')
const currentPage = ref(1)
const libraries = ref([])
const continueList = ref([])
const activeLib = ref(null)

onMounted(async () => {
  await Promise.all([loadLibs(), loadMedia(), loadContinue()])
})

async function loadLibs() {
  try {
    const res = await getFolders()
    libraries.value = res.data || []
  } catch (e) { console.error('loadLibs error:', e) }
}

async function loadMedia() {
  const params = { sort: ord.value }
  if (q.value) params.search = q.value
  if (cat.value) params.category = cat.value
  if (activeLib.value) params.folder = activeLib.value.path
  mediaStore.page = currentPage.value
  await mediaStore.fetchList(params)
}

async function loadContinue() {
  try {
    const res = await getContinue()
    continueList.value = res.data.items || []
  } catch (e) { console.error('loadContinue error:', e) }
}

function posterUrl(id) { return getPosterUrl(id) }
function go(item) { router.push('/media/' + item.id) }
function openLib(lib) { activeLib.value = lib; currentPage.value = 1; loadMedia() }
function clearLib() { activeLib.value = null; currentPage.value = 1; loadMedia() }
function doSearch() { currentPage.value = 1; loadMedia() }
function onPage(p) { currentPage.value = p; loadMedia() }
</script>

<style scoped>
.home { display: flex; flex-direction: column; gap: 36px; }
.section-title { font-size: 20px; font-weight: 700; margin-bottom: 14px; }
.section-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 10px; }
.filters { display: flex; gap: 8px; align-items: center; }
.scroll-row {
  display: flex; gap: 14px; overflow-x: auto; padding-bottom: 6px;
  scrollbar-width: thin; scrollbar-color: #333 transparent;
}
.scroll-row::-webkit-scrollbar { height: 6px; }
.scroll-row::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
.scroll-row > * { flex: 0 0 160px; }
.lib-row { display: flex; gap: 16px; flex-wrap: wrap; }
.lib-card { cursor: pointer; border-radius: 8px; overflow: hidden; transition: transform 0.2s; flex: 0 0 280px; }
.lib-card:hover { transform: scale(1.03); }
.lib-thumb { position: relative; aspect-ratio: 16/9; background: var(--bg-card); overflow: hidden; }
.lib-thumb img { width: 100%; height: 100%; object-fit: cover; opacity: 0.4; }
.lib-label { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; }
.lib-name { font-size: 20px; font-weight: 700; }
.lib-count { font-size: 12px; color: var(--text-dim); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; }
.empty { text-align: center; padding: 80px 20px; color: var(--text-muted); }
.empty p { margin-top: 12px; }
.pager { display: flex; justify-content: center; padding: 24px 0; }
</style>
