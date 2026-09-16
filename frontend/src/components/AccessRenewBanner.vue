<template>
  <div v-if="show" class="renew-wrap">
    <el-alert type="warning" :closable="false" show-icon class="renew-alert">
      <template #title>
        <span>{{ t('access.expiredTitle') }}</span>
      </template>
      <div class="renew-body">
        <p class="msg">{{ t('access.expiredMsg') }}</p>
        <div class="row">
          <el-input
            v-model="code"
            :placeholder="t('access.codePh')"
            clearable
            class="code-input"
            @keyup.enter="submit"
          />
          <el-button type="primary" :loading="busy" @click="submit">{{ t('access.renewBtn') }}</el-button>
        </div>
      </div>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
const route = useRoute()
const code = ref('')
const busy = ref(false)

const show = computed(() => {
  if (!auth.isLoggedIn || auth.isAdmin) return false
  if (route.path === '/login' || route.path === '/register') return false
  return !auth.accessActive
})

onMounted(() => {
  if (auth.isLoggedIn) auth.fetchMe()
})

async function submit() {
  const c = (code.value || '').trim()
  if (!c) {
    ElMessage.warning(t('access.codeRequired'))
    return
  }
  busy.value = true
  try {
    const data = await auth.activate(c)
    ElMessage.success(data?.message || t('access.renewOk'))
    code.value = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('access.renewFail'))
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.renew-wrap { margin-bottom: 14px; }
.renew-alert { border-radius: 10px; }
.renew-body { margin-top: 6px; }
.msg { margin: 0 0 10px; font-size: 13px; color: var(--text-dim, #666); }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.code-input { max-width: 280px; flex: 1; min-width: 180px; }
</style>
