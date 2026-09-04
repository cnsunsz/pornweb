<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="logo">
        <svg viewBox="0 0 24 24" width="28" height="28"><path d="M8 5v14l11-7z" fill="var(--accent)"/></svg>
        <span>PornWeb</span>
      </router-link>

      <nav class="nav">
        <router-link to="/" class="nav-item" :class="{active: $route.path==='/'}">
          <svg viewBox="0 0 24 24" width="20" height="20"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" fill="currentColor"/></svg>
          <span>{{ t('nav.home') }}</span>
        </router-link>
        <router-link to="/actors" class="nav-item" :class="{active: $route.path.startsWith('/actors')}">
          <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/></svg>
          <span>{{ t('nav.actors') }}</span>
        </router-link>
        <router-link v-if="auth.isAdmin" to="/settings?tab=server" class="nav-item" :class="{active: $route.path==='/settings'}">
          <svg viewBox="0 0 24 24" width="20" height="20"><path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94L14.4 2.81a.47.47 0 0 0-.47-.41h-3.85a.47.47 0 0 0-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87a.48.48 0 0 0 .12.61l2.03 1.58c-.04.31-.06.63-.06-.94s.02.63.06.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.47.41h3.85c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z" fill="currentColor"/></svg>
          <span>{{ t('nav.console') }}</span>
        </router-link>
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
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

function onCommand(cmd) {
  if (cmd === 'logout') { auth.logout(); router.push('/login') }
  if (cmd === 'settings') { router.push('/settings') }
}
</script>

<style scoped>
.header {
  background: rgba(16,16,16,0.95); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1400px; margin: 0 auto; display: flex; align-items: center;
  padding: 0 24px; height: 56px; gap: 24px;
}
.logo {
  display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700;
  color: var(--accent); white-space: nowrap;
}
.nav { display: flex; gap: 2px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 6px; padding: 8px 14px;
  border-radius: 6px; color: var(--text-dim); font-size: 14px; transition: all 0.15s;
}
.nav-item:hover, .nav-item.active { color: var(--text); background: var(--bg-hover); }
.user-btn {
  display: flex; align-items: center; gap: 8px; cursor: pointer; color: var(--text);
}
.avatar {
  width: 30px; height: 30px; border-radius: 50%; background: var(--bg-hover);
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600;
}
.name { font-size: 14px; }
</style>
