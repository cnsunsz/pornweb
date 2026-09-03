<template>
  <div class="dash">
    <aside class="side">
      <div class="side-title">{{ t('dash.title') }}</div>
      <button class="side-item" :class="{on: tab==='server'}" v-if="auth.isAdmin" @click="tab='server'">{{ t('dash.server') }}</button>
      <button class="side-item" :class="{on: tab==='users'}" v-if="auth.isAdmin" @click="tab='users'">{{ t('dash.users') }}</button>
      <button class="side-item" :class="{on: tab==='libraries'}" v-if="auth.isAdmin" @click="tab='libraries'">{{ t('dash.libraries') }}</button>
      <div class="side-title">{{ t('dash.account') }}</div>
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
        <el-alert v-if="restartHint" :title="t('dash.restartAlert')" type="warning" show-icon style="margin-top:16px" />
      </div>

      <div v-if="tab==='users' && auth.isAdmin">
        <UserManagement />
      </div>

      <div v-if="tab==='libraries' && auth.isAdmin">
        <Admin />
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
import { getServerSettings, updateServerSettings } from '@/api/settings'
import { changePassword } from '@/api/users'
import { ElMessage } from 'element-plus'
import { setLocale, SUPPORTED, apiError } from '@/i18n'
import Admin from '@/views/Admin.vue'
import UserManagement from '@/views/UserManagement.vue'

const { t, locale } = useI18n()
const langs = SUPPORTED
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const tab = ref('account')
const saving = ref(false)
const restartHint = ref(false)
const form = reactive({
  app_name: 'MediaVault',
  http_port: 8099,
  bind_host: '127.0.0.1',
  public_port: 5588,
  media_root: '',
  env_file: ''
})

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
    ? ['server', 'users', 'libraries', 'account']
    : ['account']
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
      app_name: form.app_name
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
  width: 220px; flex-shrink:0; background: #141414; border-right:1px solid var(--border);
  padding: 20px 10px;
}
.side-title { font-size:11px; letter-spacing:.08em; color:var(--text-muted); padding:12px 12px 6px; text-transform:uppercase; }
.side-item {
  display:block; width:100%; text-align:left; background:transparent; border:0; color:var(--text-dim);
  padding:10px 12px; border-radius:6px; cursor:pointer; font-size:14px;
}
.side-item:hover { background:var(--bg-hover); color:var(--text); }
.side-item.on { background: rgba(0,164,220,.15); color: var(--accent); font-weight:600; }
.pane { flex:1; padding: 24px 28px; overflow:auto; }
.pane h2 { font-size:22px; margin-bottom:8px; }
.hint { color:var(--text-dim); font-size:13px; margin-bottom:16px; }
.ch { font-weight:600; }
.note { margin-left:12px; color:var(--text-muted); font-size:12px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size:12px; color:var(--text-dim); word-break:break-all; }
</style>
