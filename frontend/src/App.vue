<template>
  <el-config-provider :locale="elLocale">
    <div class="app-container">
      <AppHeader v-if="authStore.isLoggedIn" />
      <main class="app-main" :class="{ 'app-main-wide': $route.path.startsWith('/settings') }">
        <router-view />
      </main>
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import zhTw from 'element-plus/es/locale/lang/zh-tw'
import en from 'element-plus/es/locale/lang/en'
import ja from 'element-plus/es/locale/lang/ja'

const authStore = useAuthStore()
const { locale } = useI18n()
const elLocale = computed(() => ({
  'zh-CN': zhCn,
  'zh-TW': zhTw,
  en,
  ja,
}[locale.value] || en))
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-main {
  flex: 1;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}
.app-main-wide {
  max-width: 100%;
  padding: 0;
}
</style>
