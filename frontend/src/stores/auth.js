import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, getMe, activate as apiActivate } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)
  const accessActive = computed(() => {
    if (!user.value) return false
    if (user.value.is_admin) return true
    if (typeof user.value.access_active === 'boolean') return user.value.access_active
    // legacy cached user without field → treat as active until /me refresh
    return true
  })
  const accessExpiresAt = computed(() => user.value?.access_expires_at || null)
  const accessDaysLeft = computed(() => {
    const v = user.value?.access_days_left
    return v === undefined ? null : v
  })
  
  function _persist() {
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  async function login(username, password) {
    const res = await apiLogin(username, password)
    token.value = res.data.access_token
    user.value = res.data.user
    _persist()
    return res.data
  }
  
  async function register(username, email, password, inviteCode) {
    const res = await apiRegister(username, email, password, inviteCode)
    token.value = res.data.access_token
    user.value = res.data.user
    _persist()
    return res.data
  }
  
  async function fetchMe() {
    try {
      const res = await getMe()
      user.value = res.data
      localStorage.setItem('user', JSON.stringify(user.value))
    } catch {
      logout()
    }
  }

  async function activate(inviteCode) {
    const res = await apiActivate(inviteCode)
    if (res.data?.user) {
      user.value = res.data.user
      localStorage.setItem('user', JSON.stringify(user.value))
    }
    return res.data
  }
  
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }
  
  return {
    token, user, isLoggedIn, isAdmin,
    accessActive, accessExpiresAt, accessDaysLeft,
    login, register, fetchMe, activate, logout,
  }
})
