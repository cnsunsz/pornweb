<template>
  <div class="home">
    <!-- Continue Watching strip (progress > 0) -->
    <section v-if="continueList.length" class="section">
      <div class="section-head">
        <h2 class="section-title emby-section-title">{{ t('home.continue') }}</h2>
      </div>
      <div class="emby-scroll-row">
        <MediaCard v-for="item in continueList" :key="'c-'+item.id" :item="item" @click="go(item)" />
      </div>
    </section>

    <!-- Latest added — Emby-style horizontal row (default home only) -->
    <section v-if="showLatestRow && latestList.length" class="section">
      <div class="section-head">
        <h2 class="section-title emby-section-title">{{ t('home.latestAdded') }}</h2>
      </div>
      <div class="emby-scroll-row">
        <MediaCard v-for="item in latestList" :key="'l-'+item.id" :item="item" @click="go(item)" />
      </div>
    </section>

    <!-- Category / library chips -->
    <section class="section chips-section">
      <div class="chip-row">
        <button
          class="chip"
          :class="{ on: !activeLib && !genre }"
          @click="clearFilters"
        >{{ t('home.all') }}</button>
        <button
          v-for="lib in libraries"
          :key="'lib-'+lib.path"
          class="chip"
          :class="{ on: activeLib && activeLib.path === lib.path }"
          @click="openLib(lib)"
        >{{ lib.name }} <span class="chip-n">{{ lib.count }}</span></button>
        <button
          v-for="g in genreChips"
          :key="'g-'+g"
          class="chip chip-genre"
          :class="{ on: genre === g }"
          @click="pickGenre(g)"
        >{{ g }}</button>
      </div>
    </section>

    <!-- Dense poster wall (filtered / all) -->
    <section class="section">
      <div class="section-top">
        <h2 class="section-title emby-section-title">
          {{ sectionTitle }}
          <span v-if="mediaStore.total" class="total">{{ t('home.items', { n: mediaStore.total }) }}</span>
        </h2>
        <div class="filters">
          <el-select v-model="cat" clearable :placeholder="t('home.type')" @change="doSearch" size="small" style="width:100px">
            <el-option :label="t('home.movie')" value="movie" />
            <el-option :label="t('home.show')" value="tvshow" />
          </el-select>
          <el-select v-model="ord" @change="doSearch" size="small" style="width:110px">
            <el-option :label="t('home.newest')" value="newest" />
            <el-option :label="t('home.rating')" value="rating" />
            <el-option :label="t('home.year')" value="year" />
            <el-option :label="t('home.title')" value="title" />
          </el-select>
        </div>
      </div>

      <div v-if="mediaStore.items.length" class="tube-grid">
        <MediaCard v-for="item in mediaStore.items" :key="item.id" :item="item" @click="go(item)" />
      </div>
      <div v-else-if="!mediaStore.loading" class="empty">
        <svg viewBox="0 0 24 24" width="56" height="56"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg>
        <p>{{ t('home.empty') }}</p>
        <el-button type="primary" @click="$router.push('/settings?tab=libraries')" style="margin-top:12px">{{ t('home.addLib') }}</el-button>
      </div>
      <div v-if="mediaStore.loading" class="loading">
        <el-icon :size="24" class="is-loading"><Loading /></el-icon>
      </div>

      <div v-if="mediaStore.total > mediaStore.pageSize" class="pager">
        <el-pagination
          :current-page="currentPage"
          :page-size="mediaStore.pageSize"
          :total="mediaStore.total"
          layout="prev, pager, next"
          @current-change="onPage"
          background
          small
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { getFolders, getContinue, getMediaList } from '@/api/media'
import { Loading } from '@element-plus/icons-vue'
import MediaCard from '@/components/MediaCard.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const mediaStore = useMediaStore()

const cat = ref('')
const ord = ref('newest')
const currentPage = ref(1)
const libraries = ref([])
const continueList = ref([])
const latestList = ref([])
const activeLib = ref(null)
const genre = ref('')

const genreChips = computed(() => (mediaStore.genres || []).slice(0, 16))

/* trail: show Emby "Latest added" row only on unfiltered home (no search/lib/genre) */
const showLatestRow = computed(() => {
  const q = typeof route.query.q === 'string' ? route.query.q.trim() : ''
  return !q && !activeLib.value && !genre.value
})

const sectionTitle = computed(() => {
  if (route.query.q) return t('home.searchResults', { q: route.query.q })
  if (activeLib.value) return activeLib.value.name
  if (genre.value) return genre.value
  return showLatestRow.value ? t('home.allMedia') : t('home.latest')
})

onMounted(async () => {
  await Promise.all([loadLibs(), mediaStore.fetchGenres().catch(() => {}), loadContinue(), loadLatest()])
  await loadMedia()
})

watch(() => route.query.q, () => {
  currentPage.value = 1
  loadMedia()
})

async function loadLibs() {
  try {
    const res = await getFolders()
    libraries.value = res.data || []
  } catch (e) { console.error('loadLibs error:', e) }
}

async function loadMedia() {
  const params = { sort: ord.value }
  const q = typeof route.query.q === 'string' ? route.query.q.trim() : ''
  if (q) params.search = q
  if (cat.value) params.category = cat.value
  if (genre.value) params.genre = genre.value
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

async function loadLatest() {
  try {
    // Existing list API — newest first; no API shape change
    const res = await getMediaList({ page: 1, page_size: 24, sort: 'newest' })
    latestList.value = res.data.items || []
  } catch (e) { console.error('loadLatest error:', e) }
}

function go(item) { router.push('/media/' + item.id) }
function openLib(lib) {
  activeLib.value = lib
  genre.value = ''
  currentPage.value = 1
  loadMedia()
}
function pickGenre(g) {
  genre.value = genre.value === g ? '' : g
  activeLib.value = null
  currentPage.value = 1
  loadMedia()
}
function clearFilters() {
  activeLib.value = null
  genre.value = ''
  cat.value = ''
  currentPage.value = 1
  if (route.query.q) router.push({ path: '/' })
  else loadMedia()
}
function doSearch() { currentPage.value = 1; loadMedia() }
function onPage(p) { currentPage.value = p; loadMedia() }
</script>

<style scoped>
.home { display: flex; flex-direction: column; gap: 18px; }
.section-head, .section-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; flex-wrap: wrap; gap: 6px;
}
.section-title {
  font-size: 16px; font-weight: 700; margin: 0;
  display: flex; align-items: baseline; gap: 8px;
  letter-spacing: 0.01em;
}
.total { font-size: 11px; font-weight: 600; color: var(--text-muted); }
.filters { display: flex; gap: 8px; align-items: center; }

.chip-row {
  display: flex; flex-wrap: wrap; gap: 6px;
  padding-bottom: 2px;
}
.chip {
  border: 1px solid #2a2a2a;
  background: #161616;
  color: var(--text-dim);
  padding: 4px 11px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.12s;
}
.chip:hover { border-color: var(--accent); color: var(--text); }
.chip.on {
  background: var(--accent);
  border-color: var(--accent);
  color: #111;
}
.chip-n {
  margin-left: 4px;
  opacity: 0.75;
  font-weight: 700;
}
.chip.on .chip-n { opacity: 0.85; }
.chip-genre { border-style: dashed; }

.empty { text-align: center; padding: 64px 20px; color: var(--text-muted); }
.empty p { margin-top: 12px; }
.loading { display: flex; justify-content: center; padding: 24px; color: var(--accent); }
.pager { display: flex; justify-content: center; padding: 18px 0 2px; }
</style>
