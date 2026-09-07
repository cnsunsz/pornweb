<template>
  <div class="auth-page">
    <div class="auth-glow" aria-hidden="true"></div>
    <div class="auth-card">
      <div class="auth-logo">
        <BrandLogo size="lg" breathe />
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
import BrandLogo from '@/components/BrandLogo.vue'
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
.auth-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #050505;
  padding: 24px;
  position: relative;
  overflow: hidden;
}
.auth-glow {
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(ellipse at 32% 18%, rgba(255,163,26,0.16), transparent 42%),
    radial-gradient(ellipse at 72% 88%, rgba(255,163,26,0.08), transparent 40%);
  animation: glow-pulse 5.5s ease-in-out infinite;
  pointer-events: none;
}
@keyframes glow-pulse {
  0%, 100% { opacity: 0.72; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.04); }
}
.auth-card {
  position: relative;
  z-index: 1;
  width: 400px; max-width: 100%;
  padding: 36px 32px;
  background: #121212;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,163,26,0.04);
  animation: card-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(14px) scale(0.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.auth-logo { text-align: center; margin-bottom: 28px; }
.auth-logo :deep(.brand) { justify-content: center; }
.auth-logo p { color: var(--text-dim); font-size: 14px; margin-top: 16px; }
.auth-link { text-align: center; margin-top: 18px; font-size: 14px; color: var(--text-dim); }
.auth-link a { margin-left: 6px; font-weight: 700; }
@media (prefers-reduced-motion: reduce) {
  .auth-glow { animation: none; }
  .auth-card { animation: none; }
}
</style>
