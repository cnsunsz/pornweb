import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUsers } from '@/api/users'

export const useUsersStore = defineStore('users', () => {
  const users = ref([])
  const loading = ref(false)

  async function fetchUsers() {
    loading.value = true
    try {
      const res = await getUsers()
      users.value = res.data
    } finally {
      loading.value = false
    }
  }

  return { users, loading, fetchUsers }
})
