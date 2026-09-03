<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg viewBox="0 0 24 24" width="48" height="48"><path d="M8 5v14l11-7z" fill="var(--accent)"/></svg>
        <h1>PornWeb</h1>
        <p>{{ t('auth.loginTitle') }}</p>
      </div>
      <el-form ref="formRef" :model="f" :rules="rules" @submit.prevent="submit">
        <el-form-item prop="username">
          <el-input v-model="f.username" :placeholder="t('auth.username')" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="f.password" type="password" show-password :placeholder="t('auth.password')" size="large" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="busy" @click="submit" style="width:100%">{{ t('auth.login') }}</el-button>
      </el-form>
      <div class="auth-link">{{ t('auth.noAccount') }}<router-link to="/register">{{ t('auth.register') }}</router-link></div>
    </div>
  </div>
</template>
<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { apiError } from '@/i18n'
const { t } = useI18n()
const router = useRouter(); const auth = useAuthStore()
const formRef = ref(); const busy = ref(false)
const f = reactive({ username: '', password: '' })
const rules = computed(() => ({
  username: [{ required: true, message: t('auth.userRequired') }],
  password: [{ required: true, message: t('auth.passRequired') }],
}))
async function submit() {
  try { await formRef.value.validate() } catch { return }
  busy.value = true
  try { await auth.login(f.username, f.password); ElMessage.success(t('auth.loginOk')); router.push('/') }
  catch(e) { ElMessage.error(apiError(e, t) === t('err.fail') ? (e.response?.data?.detail || t('auth.loginFail')) : apiError(e, t)) }
  finally { busy.value = false }
}
</script>
<style scoped>
.auth-page { min-height:100vh; display:flex; align-items:center; justify-content:center; background: radial-gradient(ellipse at top, #101010, #000); }
.auth-card { width:380px; padding:40px; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; }
.auth-logo { text-align:center; margin-bottom:28px; }
.auth-logo h1 { margin:12px 0 4px; font-size:22px; }
.auth-logo p { color:var(--text-dim); font-size:14px; }
.auth-link { text-align:center; margin-top:16px; font-size:14px; color:var(--text-dim); }
</style>
