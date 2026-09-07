<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="logo" :aria-label="'PornWeb'">
        <span class="logo-porn">Porn</span><span class="logo-web">Web</span>
      </router-link>

      <form class="search-wrap" @submit.prevent="goSearch">
        <input
          v-model="q"
          class="search-input"
          type="search"
          :placeholder="t('home.searchPh')"
          autocomplete="off"
        />
        <button type="submit" class="search-btn" :title="t('home.search')">
          <svg viewBox="0 0 24 24" width="18" height="18"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor"/></svg>
        </button>
      </form>

      <nav class="nav">
        <router-link to="/" class="nav-item" :class="{active: $route.path==='/'}">{{ t('nav.home') }}</router-link>
        <router-link to="/actors" class="nav-item" :class="{active: $route.path.startsWith('/actors')}">{{ t('nav.actors') }}</router-link>
        <router-link v-if="auth.isAdmin" to="/settings?tab=libraries" class="nav-item" :class="{active: $route.path==='/settings' && ($route.query.tab==='libraries' || !$route.query.tab)}">{{ t('nav.libraries') }}</router-link>
        <router-link v-if="auth.isAdmin" to="/settings?tab=server" class="nav-item" :class="{active: $route.path==='/settings' && $route.query.tab==='server'}">{{ t('nav.console') }}</router-link>
      </nav>

      <el-dropdown trigger="click" @command="onCommand">
        <span class="user-btn">
          <span class="avatar">{{ (auth.user?.username || 'U')[0].toUpperCase() }}</span>
          <span class="name">{{ auth.user?.username }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="settings">{{ t('nav.settings') }}</el-dropdown-item>
            <el-dropdown-item command="logout" divided>{{ t('nav.logout') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')

watch(() => route.query.q, (v) => {
  q.value = typeof v === 'string' ? v : ''
})

function goSearch() {
  const term = q.value.trim()
  router.push({ path: '/', query: term ? { q: term } : {} })
}

function onCommand(cmd) {
  if (cmd === 'logout') { auth.logout(); router.push('/login') }
  if (cmd === 'settings') { router.push('/settings') }
}
</script>

<style scoped>
.header {
  background: #0a0a0a;
  border-bottom: 1px solid #1f1f1f;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  max-width: 1680px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  padding: 0 14px;
  height: var(--header-h);
  gap: 12px;
}
.logo {
  display: inline-flex;
  align-items: center;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
  white-space: nowrap;
  line-height: 1;
  flex-shrink: 0;
}
.logo-porn { color: #fff; }
.logo-web {
  background: var(--accent);
  color: #111;
  padding: 3px 7px 4px;
  margin-left: 1px;
  border-radius: 3px;
  font-weight: 900;
}
.search-wrap {
  display: flex;
  flex: 1;
  max-width: 420px;
  min-width: 0;
  height: 34px;
  border: 1px solid #333;
  border-radius: 4px;
  overflow: hidden;
  background: #151515;
}
.search-wrap:focus-within { border-color: var(--accent); }
.search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--text);
  padding: 0 10px;
  font-size: 13px;
  outline: none;
}
.search-btn {
  width: 40px;
  border: 0;
  background: #222;
  color: #ccc;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.search-btn:hover { background: var(--accent); color: #111; }
.nav {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  margin-left: auto;
}
.nav-item {
  padding: 7px 10px;
  border-radius: 4px;
  color: var(--text-dim);
  font-size: 13px;
  font-weight: 600;
  transition: color 0.12s, background 0.12s;
  white-space: nowrap;
}
.nav-item:hover { color: var(--text); background: var(--bg-hover); }
.nav-item.active { color: var(--accent); }
.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text);
  flex-shrink: 0;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: #111;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
}
.name { font-size: 13px; max-width: 100px; overflow: hidden; text-overflow: ellipsis; }
@media (max-width: 820px) {
  .name { display: none; }
  .nav-item { padding: 7px 8px; font-size: 12px; }
  .search-wrap { max-width: none; }
}
@media (max-width: 560px) {
  .nav { display: none; }
}
</style>
