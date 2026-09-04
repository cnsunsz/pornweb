import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue')
  },
  {
    path: '/actors',
    name: 'Actors',
    component: () => import('@/views/Actors.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/actors/:name',
    name: 'ActorDetail',
    component: () => import('@/views/Actors.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/media/:id',
    name: 'MediaDetail',
    component: () => import('@/views/MediaDetail.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    redirect: { path: '/settings', query: { tab: 'libraries' } }
  },
  {
    path: '/users',
    redirect: { path: '/settings', query: { tab: 'users' } }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }
  if ((to.path === '/login' || to.path === '/register') && token) {
    next('/')
    return
  }
  if (to.meta.requiresAdmin) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || 'null')
      if (!user?.is_admin) {
        next('/')
        return
      }
    } catch {
      next('/login')
      return
    }
  }
  next()
})

export default router
