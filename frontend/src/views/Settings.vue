<template>
  <div class="dash">
    <aside class="side">
      <div class="side-title">{{ t('dash.title') }}</div>
      <button class="side-item" :class="{on: tab==='server'}" v-if="auth.isAdmin" @click="tab='server'">{{ t('dash.server') }}</button>
      <button class="side-item" :class="{on: tab==='users'}" v-if="auth.isAdmin" @click="tab='users'">{{ t('dash.users') }}</button>
      <button class="side-item" :class="{on: tab==='libraries'}" v-if="auth.isAdmin" @click="tab='libraries'">{{ t('dash.libraries') }}</button>
      <div class="side-title">{{ t('dash.account') }}</div>
      <button class="side-item" :class="{on: tab==='playback'}" @click="tab='playback'">{{ t('playback.title') }}</button>
      <button class="side-item" :class="{on: tab==='account'}" @click="tab='account'">{{ t('dash.myAccount') }}</button>
    </aside>

    <section class="pane">
      <div v-if="tab==='server' && auth.isAdmin">
        <h2>{{ t('dash.server') }}</h2>
        <p class="hint">{{ t('dash.serverHint') }}</p>
        <el-card>
          <template #header><span class="ch">{{ t('dash.network') }}</span></template>
          <el-form label-width="140px" style="max-width:560px">
            <el-form-item :label="t('dash.httpPort')">
              <el-input-number v-model="form.http_port" :min="1" :max="65535" :step="1" controls-position="right" />
              <span class="note">{{ t('dash.httpPortHint') }}</span>
            </el-form-item>
            <el-form-item :label="t('dash.bind')">
              <el-select v-model="form.bind_host" style="width:220px">
                <el-option :label="t('dash.bindLocal')" value="127.0.0.1" />
                <el-option :label="t('dash.bindLan')" value="0.0.0.0" />
              </el-select>
              <span class="note">{{ t('dash.bindHint') }}</span>
            </el-form-item>
            <el-form-item :label="t('dash.publicPort')">
              <el-input-number v-model="form.public_port" :min="1" :max="65535" controls-position="right" />
              <span class="note">{{ t('dash.publicHint') }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveServer">{{ t('dash.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('dash.paths') }}</span></template>
          <el-form label-width="140px" style="max-width:720px">
            <el-form-item :label="t('dash.mediaRoot')">
              <el-input v-model="form.media_root" :placeholder="t('dash.mediaRootPh')" />
            </el-form-item>
            <el-form-item :label="t('dash.envFile')">
              <span class="mono">{{ form.env_file }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveServer">{{ t('dash.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('dash.autoScan') }}</span></template>
          <p class="sub-hint">{{ t('dash.autoScanHint') }}</p>
          <el-form label-width="140px" style="max-width:560px">
            <el-form-item :label="t('dash.autoScanEnabled')">
              <el-switch v-model="form.auto_scan_enabled" />
              <span class="note">{{ t('dash.autoScanEnabledHint') }}</span>
            </el-form-item>
            <el-form-item :label="t('dash.autoScanInterval')">
              <el-input-number v-model="form.auto_scan_interval_minutes" :min="1" :max="1440" :step="5" controls-position="right" />
              <span class="note">{{ t('dash.autoScanIntervalHint') }}</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveServer">{{ t('dash.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>


        <!-- Emby / Jellyfin-style metadata settings (admin-only; already gated by tab) -->
        <el-card style="margin-top:16px" class="meta-card">
          <template #header><span class="ch">{{ t('dash.metadata') }}</span></template>
          <p class="sub-hint">{{ t('dash.metadataHint') }}</p>

          <div class="switch-list meta-top">
            <div class="switch-row" @click="form.scraper_prefer_local = !form.scraper_prefer_local">
              <div class="switch-copy">
                <span class="switch-label">{{ t('dash.preferLocal') }}</span>
                <span class="switch-desc">{{ t('dash.preferLocalHint') }}</span>
              </div>
              <el-switch v-model="form.scraper_prefer_local" @click.stop />
            </div>
            <div class="switch-row" @click="form.scraper_internet_enabled = !form.scraper_internet_enabled">
              <div class="switch-copy">
                <span class="switch-label">{{ t('dash.internetProviders') }}</span>
                <span class="switch-desc">{{ t('dash.internetProvidersHint') }}</span>
              </div>
              <el-switch v-model="form.scraper_internet_enabled" @click.stop />
            </div>
            <div class="switch-row static">
              <div class="switch-copy">
                <span class="switch-label">{{ t('dash.metaLanguage') }}</span>
                <span class="switch-desc">{{ t('dash.metaLanguageHint') }}</span>
              </div>
              <el-select v-model="form.scraper_metadata_language" style="width:160px" @click.stop>
                <el-option label="简体中文 (zh-CN)" value="zh-CN" />
                <el-option label="繁體中文 (zh-TW)" value="zh-TW" />
                <el-option label="English (en-US)" value="en-US" />
                <el-option label="日本語 (ja-JP)" value="ja-JP" />
                <el-option label="한국어 (ko-KR)" value="ko-KR" />
              </el-select>
            </div>
            <div class="switch-row" @click="form.scraper_save_artwork = !form.scraper_save_artwork">
              <div class="switch-copy">
                <span class="switch-label">{{ t('dash.saveArtwork') }}</span>
                <span class="switch-desc">{{ t('dash.saveArtworkHint') }}</span>
              </div>
              <el-switch v-model="form.scraper_save_artwork" @click.stop />
            </div>
          </div>

          <div class="provider-block" :class="{ dim: !form.scraper_internet_enabled }">
            <div class="provider-title">{{ t('dash.providersTitle') }}</div>
            <p class="provider-note">{{ t('dash.providersNote') }}</p>

            <div class="provider-row">
              <div class="provider-main" @click="expandTmdb = !expandTmdb">
                <div class="provider-info">
                  <span class="provider-name">TMDB</span>
                  <span class="provider-desc">{{ t('dash.scraperTmdbHint') }}</span>
                </div>
                <el-switch v-model="form.scraper_tmdb_enabled" :disabled="!form.scraper_internet_enabled" @click.stop />
              </div>
              <div v-show="expandTmdb || form.scraper_tmdb_enabled" class="provider-detail">
                <label class="detail-label">{{ t('dash.tmdbApiKey') }}</label>
                <el-input
                  v-model="form.tmdb_api_key"
                  type="password"
                  show-password
                  :placeholder="t('dash.tmdbApiKeyPh')"
                  :disabled="!form.scraper_internet_enabled"
                />
              </div>
            </div>

            <div class="provider-row">
              <div class="provider-main">
                <div class="provider-info">
                  <span class="provider-name">{{ t('dash.scraperDoubanName') }}</span>
                  <span class="provider-desc">{{ t('dash.scraperDoubanHint') }}</span>
                </div>
                <el-switch v-model="form.scraper_douban_enabled" :disabled="!form.scraper_internet_enabled" />
              </div>
            </div>

            <div class="provider-row">
              <div class="provider-main">
                <div class="provider-info">
                  <span class="provider-name">JavDB</span>
                  <span class="provider-desc">{{ t('dash.scraperJavdbHint') }}</span>
                </div>
                <el-switch v-model="form.scraper_javdb_enabled" :disabled="!form.scraper_internet_enabled" />
              </div>
            </div>
          </div>

          <el-collapse class="adv-collapse">
            <el-collapse-item :title="t('dash.metaAdvanced')" name="adv">
              <el-form label-width="140px" style="max-width:560px">
                <el-form-item :label="t('dash.scraperOrder')">
                  <el-input v-model="form.scraper_order" :placeholder="t('dash.scraperOrderPh')" />
                  <span class="note block">{{ t('dash.scraperOrderHint') }}</span>
                </el-form-item>
                <el-form-item :label="t('dash.scraperProxy')">
                  <el-input v-model="form.scraper_proxy" :placeholder="t('dash.scraperProxyPh')" />
                </el-form-item>
                <el-form-item :label="t('dash.scraperTimeout')">
                  <el-input-number v-model="form.scraper_timeout_seconds" :min="2" :max="30" :step="1" controls-position="right" />
                  <span class="note">{{ t('dash.scraperTimeoutHint') }}</span>
                </el-form-item>
                <el-form-item :label="t('dash.actorPhotoScrape')">
                  <el-button type="primary" plain :loading="actorPhotoScraping" @click="scrapeActorPhotosNow">{{ t('dash.actorPhotoScrapeBtn') }}</el-button>
                  <span class="note block">{{ t('dash.actorPhotoScrapeHint') }}</span>
                </el-form-item>
                <el-form-item :label="t('dash.doubanCookie')">
                  <el-input v-model="form.scraper_douban_cookie" type="textarea" :rows="2" :placeholder="t('dash.cookiePh')" />
                </el-form-item>
                <el-form-item :label="t('dash.javdbCookie')">
                  <el-input v-model="form.scraper_javdb_cookie" type="textarea" :rows="2" :placeholder="t('dash.cookiePh')" />
                </el-form-item>
              </el-form>
            </el-collapse-item>
          </el-collapse>

          <div style="margin-top:14px">
            <el-button type="primary" :loading="saving" @click="saveServer">{{ t('dash.save') }}</el-button>
          </div>
        </el-card>

        <el-alert v-if="restartHint" :title="t('dash.restartAlert')" type="warning" show-icon style="margin-top:16px" />
      </div>

      <div v-if="tab==='users' && auth.isAdmin">
        <UserManagement />
      </div>

      <div v-if="tab==='libraries' && auth.isAdmin">
        <Admin />
      </div>

      <!-- Playback settings: chip + switch layout mirroring Android PlaybackSettingsScreen -->
      <div v-if="tab==='playback'">
        <h2>{{ t('playback.title') }}</h2>
        <p class="hint">{{ t('playback.hint') }}</p>

        <el-card>
          <template #header><span class="ch">{{ t('playback.defaultSpeed') }}</span></template>
          <div class="chip-row">
            <button
              v-for="s in speedOptions"
              :key="'ds'+s"
              type="button"
              class="chip"
              :class="{ on: prefs.defaultSpeed === s }"
              @click="prefs.defaultSpeed = s"
            >{{ s === 1 ? '1.0x' : s + 'x' }}</button>
          </div>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('playback.longPressSpeed') }}</span></template>
          <p class="sub-hint">{{ t('playback.longPressHint') }}</p>
          <div class="chip-row">
            <button
              v-for="s in longPressOptions"
              :key="'lp'+s"
              type="button"
              class="chip"
              :class="{ on: prefs.longPressSpeed === s }"
              @click="prefs.longPressSpeed = s"
            >{{ s }}x</button>
          </div>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('playback.skipSeconds') }}</span></template>
          <p class="sub-hint">{{ t('playback.skipHint') }}</p>
          <div class="chip-row">
            <button
              v-for="s in skipOptions"
              :key="'sk'+s"
              type="button"
              class="chip"
              :class="{ on: prefs.skipSeconds === s }"
              @click="prefs.skipSeconds = s"
            >{{ s }}s</button>
          </div>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('playback.swipeSeek') }}</span></template>
          <p class="sub-hint">{{ t('playback.swipeHint') }}</p>
          <div class="chip-row">
            <button
              v-for="s in swipeOptions"
              :key="'sw'+s"
              type="button"
              class="chip"
              :class="{ on: prefs.swipeSeekSeconds === s }"
              @click="prefs.swipeSeekSeconds = s"
            >{{ s }}s</button>
          </div>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('playback.switches') }}</span></template>
          <div class="switch-list">
            <div class="switch-row" @click="prefs.doubleTapSeek = !prefs.doubleTapSeek">
              <span>{{ t('playback.doubleTap') }}</span>
              <el-switch v-model="prefs.doubleTapSeek" @click.stop />
            </div>
            <div class="switch-row" @click="prefs.leftLongPressRewind = !prefs.leftLongPressRewind">
              <span>{{ t('playback.leftRewind') }}</span>
              <el-switch v-model="prefs.leftLongPressRewind" @click.stop />
            </div>
            <div class="switch-row" @click="prefs.autoFullscreen = !prefs.autoFullscreen">
              <span>{{ t('playback.autoFullscreen') }}</span>
              <el-switch v-model="prefs.autoFullscreen" @click.stop />
            </div>
            <div class="switch-row" @click="prefs.resumeOnOpen = !prefs.resumeOnOpen">
              <span>{{ t('playback.resumeOnOpen') }}</span>
              <el-switch v-model="prefs.resumeOnOpen" @click.stop />
            </div>
          </div>
        </el-card>

        <p class="foot-hint">{{ t('playback.footHint') }}</p>
      </div>

      <div v-if="tab==='account'">
        <h2>{{ t('dash.myAccount') }}</h2>
        <el-card>
          <template #header><span class="ch">{{ t('dash.profile') }}</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item :label="t('auth.username')">{{ auth.user?.username }}</el-descriptions-item>
            <el-descriptions-item :label="t('auth.email')">{{ auth.user?.email }}</el-descriptions-item>
            <el-descriptions-item :label="t('dash.role')"><el-tag :type="auth.isAdmin?'danger':'info'" size="small">{{ auth.isAdmin ? t('dash.admin') : t('dash.user') }}</el-tag></el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('dash.language') }}</span></template>
          <p class="hint">{{ t('dash.languageHint') }}</p>
          <el-select :model-value="locale" style="width:220px" @change="onLang">
            <el-option v-for="l in langs" :key="l.code" :label="l.label" :value="l.code" />
          </el-select>
        </el-card>
        <el-card style="margin-top:16px">
          <template #header><span class="ch">{{ t('dash.changePw') }}</span></template>
          <el-form :model="pw" :rules="pwRules" ref="pwRef" label-width="80px" style="max-width:360px">
            <el-form-item :label="t('dash.oldPw')" prop="old_password"><el-input v-model="pw.old_password" type="password" show-password /></el-form-item>
            <el-form-item :label="t('dash.newPw')" prop="new_password"><el-input v-model="pw.new_password" type="password" show-password /></el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwBusy" @click="changePw">{{ t('dash.save') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { scrapeActorPhotos } from '@/api/actors'
import { getServerSettings, updateServerSettings } from '@/api/settings'
import { changePassword } from '@/api/users'
import { ElMessage } from 'element-plus'
import { setLocale, SUPPORTED, apiError } from '@/i18n'
import { usePlayerPrefs } from '@/composables/usePlayerPrefs'
import Admin from '@/views/Admin.vue'
import UserManagement from '@/views/UserManagement.vue'

const { t, locale } = useI18n()
const langs = SUPPORTED
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const prefs = usePlayerPrefs()
const tab = ref('account')
const actorPhotoScraping = ref(false)
const saving = ref(false)
const restartHint = ref(false)
const form = reactive({
  app_name: 'PornWeb',
  http_port: 8099,
  bind_host: '127.0.0.1',
  public_port: 5588,
  media_root: '',
  auto_scan_enabled: true,
  auto_scan_interval_minutes: 15,
  scraper_prefer_local: true,
  scraper_internet_enabled: true,
  scraper_metadata_language: 'zh-CN',
  scraper_save_artwork: false,
  scraper_douban_enabled: false,
  scraper_tmdb_enabled: false,
  scraper_javdb_enabled: false,
  tmdb_api_key: '',
  scraper_order: 'nfo,tmdb,douban,javdb',
  scraper_douban_cookie: '',
  scraper_javdb_cookie: '',
  scraper_proxy: '',
  scraper_timeout_seconds: 8,
  env_file: ''
})
const expandTmdb = ref(false)

const speedOptions = [0.75, 1.0, 1.25, 1.5, 2.0]
const longPressOptions = [2, 3, 4]
const skipOptions = [5, 10, 15, 30]
const swipeOptions = [60, 90, 120, 180]

const pwRef = ref()
const pwBusy = ref(false)
const pw = reactive({ old_password: '', new_password: '' })
const pwRules = computed(() => ({
  old_password: [{ required: true, message: t('dash.oldPwReq') }],
  new_password: [{ required: true, message: t('auth.passRequired') }, { min: 6, message: t('auth.passMin') }]
}))

function onLang(code) { setLocale(code) }

function applyTab(q) {
  const key = Array.isArray(q) ? q[0] : q
  const allowed = auth.isAdmin
    ? ['server', 'users', 'libraries', 'playback', 'account']
    : ['playback', 'account']
  tab.value = allowed.includes(key) ? key : (auth.isAdmin ? 'server' : 'account')
}

watch(() => route.query.tab, (q) => applyTab(q), { immediate: true })
watch(tab, (v) => {
  if (route.query.tab !== v) router.replace({ path: '/settings', query: { tab: v } })
})

onMounted(async () => {
  if (auth.isAdmin) {
    try {
      const res = await getServerSettings()
      Object.assign(form, res.data)
    } catch (e) {
      console.error(e)
    }
  }
})

async function saveServer() {
  saving.value = true
  try {
    const res = await updateServerSettings({
      http_port: form.http_port,
      bind_host: form.bind_host,
      public_port: form.public_port,
      media_root: form.media_root,
      app_name: form.app_name,
      auto_scan_enabled: form.auto_scan_enabled,
      auto_scan_interval_minutes: form.auto_scan_interval_minutes,
      scraper_prefer_local: form.scraper_prefer_local,
      scraper_internet_enabled: form.scraper_internet_enabled,
      scraper_metadata_language: form.scraper_metadata_language,
      scraper_save_artwork: form.scraper_save_artwork,
      scraper_douban_enabled: form.scraper_douban_enabled,
      scraper_tmdb_enabled: form.scraper_tmdb_enabled,
      scraper_javdb_enabled: form.scraper_javdb_enabled,
      tmdb_api_key: form.tmdb_api_key,
      scraper_order: form.scraper_order,
      scraper_douban_cookie: form.scraper_douban_cookie,
      scraper_javdb_cookie: form.scraper_javdb_cookie,
      scraper_proxy: form.scraper_proxy,
      scraper_timeout_seconds: form.scraper_timeout_seconds
    })
    Object.assign(form, res.data)
    restartHint.value = !!res.data.restart_required
    ElMessage.success(res.data.restart_required ? t('dash.savedRestart') : t('dash.saved'))
  } catch (e) {
    ElMessage.error(apiError(e, t))
  } finally { saving.value = false }
}

async function changePw() {
  try { await pwRef.value.validate() } catch { return }
  pwBusy.value = true
  try {
    await changePassword({ old_password: pw.old_password, new_password: pw.new_password })
    ElMessage.success(t('dash.pwOk'))
    pw.old_password = ''
    pw.new_password = ''
  } catch (e) {
    ElMessage.error(apiError(e, t))
  } finally { pwBusy.value = false }
}
</script>

<style scoped>
.dash { display:flex; gap:0; min-height:calc(100vh - 56px); }
.side {
  width: 220px; flex-shrink:0; background: #0e0e0e; border-right:1px solid var(--border);
  padding: 20px 10px;
}
.side-title { font-size:11px; letter-spacing:.08em; color:var(--text-muted); padding:12px 12px 6px; text-transform:uppercase; }
.side-item {
  display:block; width:100%; text-align:left; background:transparent; border:0; color:var(--text-dim);
  padding:10px 12px; border-radius:6px; cursor:pointer; font-size:14px;
}
.side-item:hover { background:var(--bg-hover); color:var(--text); }
.side-item.on { background: var(--accent-soft); color: var(--accent); font-weight:700; }
.pane { flex:1; padding: 24px 28px; overflow:auto; }
.pane h2 { font-size:22px; margin-bottom:8px; }
.hint { color:var(--text-dim); font-size:13px; margin-bottom:16px; }
.sub-hint { color:var(--text-muted); font-size:12px; margin: -4px 0 10px; }
.foot-hint { color:var(--text-muted); font-size:12px; margin-top:16px; line-height:1.6; }
.ch { font-weight:600; }
.note { margin-left:12px; color:var(--text-muted); font-size:12px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size:12px; color:var(--text-dim); word-break:break-all; }

.chip-row { display:flex; flex-wrap:wrap; gap:8px; }
.chip {
  border: 1px solid var(--border); background: var(--bg); color: var(--text-dim);
  padding: 8px 14px; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 600;
}
.chip:hover { border-color: var(--accent); color: var(--text); }
.chip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }

.switch-list { display:flex; flex-direction:column; }
.switch-row {
  display:flex; align-items:center; justify-content:space-between; gap:16px;
  padding: 12px 0; border-bottom: 1px solid var(--border); cursor: pointer; font-size: 14px;
}
.switch-row:last-child { border-bottom: 0; }
.switch-row.static { cursor: default; }
.switch-copy { display:flex; flex-direction:column; gap:2px; min-width:0; flex:1; }
.switch-label { font-size:14px; color:var(--text); }
.switch-desc { font-size:12px; color:var(--text-muted); line-height:1.45; }
.meta-top { margin-bottom: 8px; }
.provider-block { margin-top: 12px; border:1px solid var(--border); border-radius:8px; padding:10px 12px; background:#0a0a0a; }
.provider-block.dim { opacity: 0.55; pointer-events: none; }
.provider-title { font-weight:700; font-size:13px; margin-bottom:4px; }
.provider-note { font-size:12px; color:var(--text-muted); margin:0 0 10px; line-height:1.5; }
.provider-row { border-top:1px solid var(--border); padding:10px 0; }
.provider-row:first-of-type { border-top:0; padding-top:4px; }
.provider-main { display:flex; align-items:center; justify-content:space-between; gap:16px; cursor:pointer; }
.provider-info { display:flex; flex-direction:column; gap:2px; min-width:0; }
.provider-name { font-weight:700; font-size:14px; }
.provider-desc { font-size:12px; color:var(--text-muted); }
.provider-detail { margin-top:10px; padding:10px 12px; background:var(--bg-hover); border-radius:6px; }
.detail-label { display:block; font-size:12px; color:var(--text-dim); margin-bottom:6px; }
.adv-collapse { margin-top:14px; border:none; }
.note.block { display:block; margin:6px 0 0; margin-left:0; }
</style>
