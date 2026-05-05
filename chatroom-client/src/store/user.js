import { defineStore } from 'pinia'
import { login as loginApi, register as registerApi, getCurrentUser } from '../api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null')
  }),
  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user,
    userId: (state) => state.user?.id,
    username: (state) => state.user?.username,
    nickname: (state) => state.user?.nickname || state.user?.username
  },
  actions: {
    async login(data) {
      const result = await loginApi(data)
      this.token = result.token
      this.user = result.user
      localStorage.setItem('token', result.token)
      localStorage.setItem('user', JSON.stringify(result.user))
      return result
    },
    async register(data) {
      const result = await registerApi(data)
      this.token = result.token
      this.user = result.user
      localStorage.setItem('token', result.token)
      localStorage.setItem('user', JSON.stringify(result.user))
      return result
    },
    async fetchUser() {
      const user = await getCurrentUser()
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})
