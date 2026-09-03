<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <svg viewBox="0 0 24 24" width="48" height="48"><path d="M8 5v14l11-7z" fill="var(--accent)"/></svg>
        <h1>MediaVault</h1>
        <p>{{ t('auth.registerTitle') }}</p>
      </div>
      <el-form ref="formRef" :model="f" :rules="rules" @submit.prevent="submit">
        <el-form-item prop="username">
          <el-input v-model="f.username" :placeholder="t('auth.username')" size="large" />
        </el-form-item>
        <el-form-item prop="email">
          <el-input v-model="f.email" :placeholder="t('auth.email')" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="f.password" type="password" show-password :placeholder="t('auth.password')" size="large" />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input v-model="f.confirm" type="password" show-password :placeholder="t('auth.confirm')" size="large" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="busy" @click="submit" style="width:100%">{{ t('auth.register') }}</el-button>
      </el-form>
      <div class="auth-link">{{ t('auth.hasAccount') }}<router-link to="/login">{{ t('auth.login') }}</router-link></div>
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
const f = reactive({ username:'', email:'', password:'', confirm:'' })
const rules = computed(() => ({
  username: [{ required: true, message: t('auth.userRequired') }, { min: 2, max: 20, message: t('auth.userLen') }],
  email: [{ required: true, message: t('auth.emailRequired') }, { type: 'email', message: t('auth.emailInvalid') }],
  password: [{ required: true, message: t('auth.passRequired') }, { min: 6, message: t('auth.passMin') }],
  confirm: [{ required: true, message: t('auth.confirmRequired') }, { validator: (r, v, cb) => v !== f.password ? cb(new Error(t('auth.passMismatch'))) : cb() }],
}))
async function submit() {
  try { await formRef.value.validate() } catch { return }
  busy.value = true
  try { await auth.register(f.username, f.email, f.password); ElMessage.success(t('auth.registerOk')); router.push('/') }
  catch(e) { ElMessage.error(apiError(e, t) === t('err.fail') ? (e.response?.data?.detail || t('auth.registerFail')) : apiError(e, t)) }
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
