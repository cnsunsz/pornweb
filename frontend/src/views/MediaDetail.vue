<template>
  <div class="detail" v-if="item">
    <!-- Emby-style backdrop banner -->
    <div class="banner">
      <div v-if="fanartSrc" class="banner-img" :style="bgStyle"></div>
      <div class="banner-fade"></div>
      <div class="banner-inner">
        <div class="poster" @click="play">
          <img v-if="posterSrc" :src="posterSrc" :alt="item.title" />
          <div v-else class="ph">
            <svg viewBox="0 0 24 24" width="48" height="48"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#444"/></svg>
          </div>
          <div class="poster-play">
            <svg viewBox="0 0 24 24" width="28" height="28"><path d="M8 5v14l11-7z" fill="#111"/></svg>
          </div>
        </div>
        <div class="info">
          <h1>{{ item.title }}</h1>
          <p v-if="item.original_title && item.original_title!==item.title" class="sub">{{ item.original_title }}</p>
          <div class="tags">
            <span v-if="item.year" class="pill">{{ item.year }}</span>
            <span class="pill accent">{{ item.category==='tvshow'?t('home.show'):t('home.movie') }}</span>
            <span v-if="durationLabel" class="pill">{{ durationLabel }}</span>
            <span v-if="item.rating" class="rate">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="var(--accent)"/></svg>
              {{ Number(item.rating).toFixed(1) }}
            </span>
          </div>
          <div class="genre" v-if="item.genre">
            <span v-for="g in item.genre.split(',')" :key="g" class="genre-chip">{{ g.trim() }}</span>
          </div>
          <p v-if="item.director" class="dim"><strong>{{ t('media.director') }}</strong> {{ item.director }}</p>
          <div class="btns">
            <el-button type="primary" size="large" @click="play">
              <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px"><path d="M8 5v14l11-7z" fill="#111"/></svg>
              {{ t('media.play') }}
            </el-button>
            <el-button v-if="savedPos>0" size="large" @click="play">{{ t('media.resume', { time: fmtTime(savedPos) }) }}</el-button>
            <el-button v-if="auth.isAdmin" size="large" :loading="scraping" @click="doScrape">{{ t('media.scrape') }}</el-button>
          </div>
          <div v-if="parts.length>1" class="parts">
            <button
              v-for="(p,i) in parts"
              :key="i"
              class="part-btn"
              :class="{ on: partIndex===i }"
              @click="playPart(i)"
            >{{ p.label || t('media.part', { n: i+1 }) }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="body">
      <section v-if="item.plot" class="block plot">
        <h2 class="section-title">{{ t('media.plot') }}</h2>
        <p>{{ item.plot }}</p>
      </section>

      <!-- Emby-style cast photo wall -->
      <section v-if="cast.length" class="block cast-wall">
        <h2 class="section-title">{{ t('media.cast') }}</h2>
        <div class="cast-scroll">
          <router-link
            v-for="name in cast"
            :key="name"
            class="cast-card"
            :to="{ name: 'ActorDetail', params: { name } }"
          >
            <div class="cast-thumb">
              <img
                :src="actorPhoto(name)"
                :alt="name"
                loading="lazy"
                @error="onCastImgErr($event)"
              />
              <div class="cast-fallback" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="36" height="36"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" fill="#555"/></svg>
              </div>
            </div>
            <div class="cast-name" :title="name">{{ name }}</div>
          </router-link>
        </div>
      </section>

      <section v-if="related.length" class="block related">
        <h2 class="section-title">{{ t('media.related') }}</h2>
        <div class="tube-grid">
          <MediaCard v-for="r in related" :key="r.id" :item="r" @click="go(r)" />
        </div>
      </section>
    </div>

    <VideoPlayer
      v-if="playing"
      :src="streamUrl"
      :title="item.title"
      :media-id="item.id"
      :part="partIndex"
      :parts="parts"
      @close="playing=false"
      @part="playPart"
    />
  </div>
  <div v-else class="loading"><el-icon :size="32" class="is-loading"><Loading /></el-icon></div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { getStreamUrl, getPosterUrl, getFanartUrl, getMediaList, scrapeMedia } from '@/api/media'
import { getActorPhotoUrl } from '@/api/actors'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { apiError } from '@/i18n'
import { Loading } from '@element-plus/icons-vue'
import VideoPlayer from '@/components/VideoPlayer.vue'
import MediaCard from '@/components/MediaCard.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useMediaStore()
const auth = useAuthStore()
const item = ref(null)
const playing = ref(false)
const partIndex = ref(0)
const related = ref([])
const scraping = ref(false)

const parts = computed(() => item.value?.extra_files || [])
const streamUrl = computed(() => item.value ? getStreamUrl(item.value.id, partIndex.value) : '')
const posterSrc = computed(() => {
  if (!item.value) return ''
  return item.value.poster_url || item.value.id ? getPosterUrl(item.value.id) : ''
})
const fanartSrc = computed(() => {
  if (!item.value) return ''
  // Always same-origin fanart API (hotlink-safe)
  return item.value.fanart_url || item.value.id ? getFanartUrl(item.value.id) : ''
})
const cast = computed(() => {
  try {
    const raw = JSON.parse(item.value?.cast_list || '[]')
    if (!Array.isArray(raw)) return []
    const names = []
    const seen = new Set()
    for (const x of raw) {
      let n = ''
      if (typeof x === 'string') n = x.trim()
      else if (x && typeof x === 'object') n = String(x.name || x.Name || '').trim()
      if (!n || seen.has(n)) continue
      seen.add(n)
      names.push(n)
    }
    return names
  } catch {
    return []
  }
})
const savedPos = computed(() => item.value ? Number(item.value.progress || localStorage.getItem('mv_pos_' + item.value.id) || 0) : 0)
const bgStyle = computed(() => fanartSrc.value ? { backgroundImage: 'url(' + fanartSrc.value + ')' } : {})
const durationLabel = computed(() => {
  const s = Number(item.value?.duration) || 0
  if (s <= 0) return ''
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
})

function actorPhoto(name) {
  return getActorPhotoUrl(name)
}

function onCastImgErr(e) {
  // Hide broken image; gray silhouette fallback underneath stays (UI chrome, not a fake photo)
  e.target.style.display = 'none'
}

async function load() {
  playing.value = false
  item.value = await store.fetchDetail(route.params.id)
  if (item.value?.progress_part) partIndex.value = item.value.progress_part
  await loadRelated()
}

async function loadRelated() {
  related.value = []
  if (!item.value) return
  try {
    const firstGenre = (item.value.genre || '').split(',')[0]?.trim()
    const params = { page: 1, page_size: 18, sort: 'newest' }
    if (firstGenre) params.genre = firstGenre
    else if (item.value.folder) params.folder = item.value.folder
    const res = await getMediaList(params)
    related.value = (res.data.items || []).filter((x) => x.id !== item.value.id).slice(0, 12)
  } catch (e) {
    console.error('related', e)
  }
}

onMounted(load)
watch(() => route.params.id, load)

async function doScrape() {
  if (!item.value) return
  scraping.value = true
  try {
    const res = await scrapeMedia(item.value.id, { force: false })
    const data = res.data || {}
    if (data.item) item.value = data.item
    if ((data.changed || []).length) ElMessage.success(t('media.scrapeOk'))
    else ElMessage.info(t('media.scrapeNone'))
  } catch (e) {
    ElMessage.error(apiError(e, t) || t('media.scrapeFail'))
  } finally {
    scraping.value = false
  }
}

function play() { playing.value = true }
function playPart(i) { partIndex.value = i; playing.value = true }
function go(r) { router.push('/media/' + r.id) }
function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m + ':' + String(sec).padStart(2, '0')
}
</script>

<style scoped>
.detail { position: relative; min-height: calc(100vh - 80px); margin: 0 -16px; }
.banner {
  position: relative;
  min-height: 340px;
  padding: 28px 20px 32px;
  overflow: hidden;
}
.banner-img {
  position: absolute; inset: 0;
  background-size: cover; background-position: center 20%;
  filter: brightness(0.45);
  transform: scale(1.02);
}
.banner-fade {
  position: absolute; inset: 0;
  background: linear-gradient(90deg, rgba(10,10,10,0.92) 0%, rgba(10,10,10,0.55) 45%, rgba(10,10,10,0.35) 100%),
              linear-gradient(to top, var(--bg, #0d0d0d) 0%, transparent 42%);
}
.banner-inner {
  position: relative; z-index: 1;
  display: flex; gap: 28px; align-items: flex-end;
  max-width: 1200px; margin: 0 auto;
}
.poster {
  flex-shrink: 0; width: 200px; position: relative;
  border-radius: 8px; overflow: hidden;
  box-shadow: 0 8px 28px rgba(0,0,0,0.55);
  border: 1px solid rgba(255,255,255,0.08);
  cursor: pointer;
}
.poster img { width: 100%; display: block; aspect-ratio: 2/3; object-fit: cover; }
.ph {
  width: 200px; aspect-ratio: 2/3; background: #1a1a1a;
  display: flex; align-items: center; justify-content: center;
}
.poster-play {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.4); opacity: 0; transition: opacity 0.15s;
}
.poster:hover .poster-play { opacity: 1; }
.poster-play svg {
  background: var(--accent); border-radius: 50%; padding: 12px;
  width: 52px; height: 52px; box-sizing: content-box;
}
.info { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; padding-bottom: 4px; }
.info h1 {
  font-size: 32px; font-weight: 800; line-height: 1.2;
  text-shadow: 0 2px 12px rgba(0,0,0,0.6);
}
.sub { color: #bbb; font-size: 14px; }
.tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pill {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  background: rgba(255,255,255,0.1); color: #eee; font-size: 12px; font-weight: 600;
}
.pill.accent { background: var(--accent); color: #111; }
.rate {
  display: flex; align-items: center; gap: 4px;
  color: var(--accent); font-size: 15px; font-weight: 800;
}
.genre { display: flex; gap: 6px; flex-wrap: wrap; }
.genre-chip {
  padding: 2px 8px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.15);
  color: #ccc; font-size: 12px;
}
.dim { color: #ccc; font-size: 13px; }
.dim strong { color: #fff; margin-right: 6px; }
.btns { display: flex; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.parts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.part-btn {
  border: 1px solid #444; background: rgba(0,0,0,0.35); color: #ddd;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600;
}
.part-btn.on, .part-btn:hover { border-color: var(--accent); color: var(--accent); }

.body { max-width: 1200px; margin: 0 auto; padding: 8px 20px 40px; }
.block { margin-top: 28px; }
.section-title { font-size: 18px; font-weight: 800; margin-bottom: 14px; }
.plot p { color: var(--text-dim); font-size: 14px; line-height: 1.75; max-width: 900px; }

/* Emby cast photo wall */
.cast-scroll {
  display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px;
  scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch;
}
.cast-scroll::-webkit-scrollbar { height: 6px; }
.cast-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
.cast-card {
  flex: 0 0 120px; width: 120px; text-decoration: none; color: inherit;
  scroll-snap-align: start; transition: transform 0.12s;
}
.cast-card:hover { transform: translateY(-2px); }
.cast-thumb {
  position: relative; width: 120px; height: 120px;
  border-radius: 50%; overflow: hidden;
  background: #1a1a1a; border: 2px solid #2a2a2a;
}
.cast-card:hover .cast-thumb { border-color: var(--accent); }
.cast-thumb img {
  position: relative; z-index: 1;
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.cast-fallback {
  position: absolute; inset: 0; z-index: 0;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(145deg, #1e1e1e, #151515);
}
.cast-name {
  margin-top: 8px; font-size: 13px; font-weight: 600; text-align: center;
  color: var(--text); line-height: 1.3;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.cast-card:hover .cast-name { color: var(--accent); }

.related { margin-top: 32px; }
.loading { display: flex; justify-content: center; padding: 80px; color: var(--accent); }

@media (max-width: 720px) {
  .banner { padding: 20px 16px 24px; }
  .banner-inner { flex-direction: column; align-items: center; }
  .poster, .ph { width: 160px; }
  .info { align-items: center; text-align: center; }
  .info h1 { font-size: 22px; }
  .tags, .genre, .btns, .parts { justify-content: center; }
  .body { padding: 8px 16px 32px; }
  .cast-card, .cast-thumb { flex-basis: 88px; width: 88px; }
  .cast-thumb { height: 88px; }
}
</style>
