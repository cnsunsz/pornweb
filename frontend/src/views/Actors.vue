<template>
  <div class="actors">
    <!-- Actor works -->
    <template v-if="actorName">
      <div class="section-top">
        <div class="title-row">
          <el-button text @click="backToList">← {{ t('actors.back') }}</el-button>
          <h2 class="section-title">{{ actorName }}</h2>
          <span class="count" v-if="total != null">{{ t('actors.works', { n: total }) }}</span>
        </div>
        <div class="filters">
          <el-select v-model="ord" @change="loadWorks" size="small" style="width:100px">
            <el-option :label="t('home.newest')" value="newest" />
            <el-option :label="t('home.rating')" value="rating" />
            <el-option :label="t('home.year')" value="year" />
            <el-option :label="t('actors.sortTitle')" value="title" />
          </el-select>
        </div>
      </div>

      <div v-if="works.length" class="grid">
        <MediaCard v-for="item in works" :key="item.id" :item="item" @click="goMedia(item)" />
      </div>
      <div v-else-if="!loading" class="empty">
        <p>{{ t('actors.noWorks') }}</p>
      </div>
      <div v-if="loading" class="loading">
        <el-icon :size="24" class="is-loading"><Loading /></el-icon>
      </div>
      <div v-if="total > pageSize" class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="onPage"
          background
          small
        />
      </div>
    </template>

    <!-- Actor directory -->
    <template v-else>
      <div class="section-top">
        <h2 class="section-title">{{ t('actors.title') }}</h2>
        <el-input
          v-model="q"
          :placeholder="t('actors.search')"
          clearable
          size="small"
          style="width:220px"
          @input="onFilter"
        />
      </div>

      <div v-if="filtered.length" class="actor-grid">
        <div
          v-for="a in filtered"
          :key="a.name"
          class="actor-card"
          @click="openActor(a.name)"
        >
          <div class="thumb">
            <img
              v-if="posterSrc(a)"
              :src="posterSrc(a)"
              :alt="a.name"
              @error="onImgErr($event)"
            />
            <div v-else class="ph">{{ a.name.slice(0, 1) }}</div>
          </div>
          <div class="meta">
            <div class="name">{{ a.name }}</div>
            <div class="n">{{ t('actors.works', { n: a.count }) }}</div>
          </div>
        </div>
      </div>
      <div v-else-if="!loading" class="empty">
        <p>{{ t('actors.empty') }}</p>
      </div>
      <div v-if="loading" class="loading">
        <el-icon :size="24" class="is-loading"><Loading /></el-icon>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loading } from '@element-plus/icons-vue'
import MediaCard from '@/components/MediaCard.vue'
import { getActors, getActorMedia } from '@/api/actors'
import { getPosterUrl } from '@/api/media'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const actors = ref([])
const q = ref('')
const works = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 40
const ord = ref('newest')

const actorName = computed(() => {
  const n = route.params.name
  if (!n) return ''
  try {
    return decodeURIComponent(String(n))
  } catch {
    return String(n)
  }
})

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return actors.value
  return actors.value.filter((a) => a.name.toLowerCase().includes(s))
})

function posterSrc(a) {
  if (a.poster_media_id) return getPosterUrl(a.poster_media_id)
  return ''
}

function onImgErr(e) {
  e.target.style.display = 'none'
}

function openActor(name) {
  router.push({ name: 'ActorDetail', params: { name } })
}

function backToList() {
  router.push({ name: 'Actors' })
}

function goMedia(item) {
  router.push('/media/' + item.id)
}

function onFilter() {
  /* client-side filter via computed */
}

async function loadActors() {
  loading.value = true
  try {
    const res = await getActors()
    actors.value = res.data.items || []
  } catch (e) {
    console.error('loadActors', e)
    actors.value = []
  } finally {
    loading.value = false
  }
}

async function loadWorks() {
  if (!actorName.value) return
  loading.value = true
  try {
    const res = await getActorMedia(actorName.value, {
      page: page.value,
      page_size: pageSize,
      sort: ord.value,
    })
    works.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('loadWorks', e)
    works.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onPage(p) {
  page.value = p
  loadWorks()
}

watch(
  () => route.params.name,
  (n) => {
    page.value = 1
    if (n) loadWorks()
    else loadActors()
  }
)

onMounted(() => {
  if (actorName.value) loadWorks()
  else loadActors()
})
</script>

<style scoped>
.actors { display: flex; flex-direction: column; gap: 8px; }
.section-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px; flex-wrap: wrap; gap: 10px;
}
.title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.section-title { font-size: 20px; font-weight: 700; margin: 0; }
.count { color: var(--text-dim); font-size: 13px; }
.filters { display: flex; gap: 8px; align-items: center; }
.actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 16px;
}
.actor-card {
  cursor: pointer; border-radius: 8px; overflow: hidden;
  background: var(--bg-card); transition: transform 0.15s, box-shadow 0.15s;
}
.actor-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0,0,0,0.4); }
.thumb {
  aspect-ratio: 2/3; background: #1a1a1a; position: relative; overflow: hidden;
}
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.ph {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 36px; font-weight: 700; color: #555;
  background: linear-gradient(135deg, #1a1a2e, #16213e);
}
.meta { padding: 8px 8px 10px; }
.name {
  font-size: 13px; font-weight: 600; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.n { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; }
.empty { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.loading { display: flex; justify-content: center; padding: 40px; color: var(--accent); }
.pager { display: flex; justify-content: center; padding: 24px 0; }
</style>
