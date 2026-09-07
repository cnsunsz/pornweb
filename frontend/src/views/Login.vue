<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <div class="wordmark"><span class="p">Porn</span><span class="w">Web</span></div>
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
.auth-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(ellipse at 30% 0%, rgba(255,163,26,0.12), transparent 50%),
    radial-gradient(ellipse at 70% 100%, rgba(255,163,26,0.06), transparent 45%),
    #050505;
  padding: 24px;
}
.auth-card {
  width: 400px; max-width: 100%;
  padding: 36px 32px;
  background: #121212;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.55);
}
.auth-logo { text-align: center; margin-bottom: 28px; }
.wordmark {
  display: inline-flex; align-items: center;
  font-size: 32px; font-weight: 900; letter-spacing: -0.02em; line-height: 1;
}
.wordmark .p { color: #fff; }
.wordmark .w {
  background: var(--accent); color: #111;
  padding: 4px 8px 5px; margin-left: 2px; border-radius: 4px;
}
.auth-logo p { color: var(--text-dim); font-size: 14px; margin-top: 14px; }
.auth-link { text-align: center; margin-top: 18px; font-size: 14px; color: var(--text-dim); }
.auth-link a { margin-left: 6px; font-weight: 700; }
</style>
