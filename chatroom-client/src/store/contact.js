import { defineStore } from 'pinia'
import { getFriendList, getPendingRequests } from '../api/friend'
import { getMyGroups } from '../api/group'

export const useContactStore = defineStore('contact', {
  state: () => ({
    friends: [],
    groups: [],
    pendingRequests: [],
    activeContact: null,
    loading: false
  }),
  getters: {
    friendList: (state) => state.friends,
    groupList: (state) => state.groups,
    hasPendingRequests: (state) => state.pendingRequests.length > 0
  },
  actions: {
    async fetchFriends() {
      try {
        this.friends = await getFriendList()
      } catch (e) {
        console.error('Failed to fetch friends:', e)
      }
    },
    async fetchGroups() {
      try {
        this.groups = await getMyGroups()
      } catch (e) {
        console.error('Failed to fetch groups:', e)
      }
    },
    async fetchPendingRequests() {
      try {
        this.pendingRequests = await getPendingRequests()
      } catch (e) {
        console.error('Failed to fetch pending requests:', e)
      }
    },
    async fetchAll() {
      this.loading = true
      try {
        await Promise.all([
          this.fetchFriends(),
          this.fetchGroups(),
          this.fetchPendingRequests()
        ])
      } finally {
        this.loading = false
      }
    },
    setActiveContact(contact) {
      this.activeContact = contact
    },
    // Update friend's online status from WebSocket presence
    updateFriendStatus(userId, online) {
      const friend = this.friends.find(f => f.friendId === userId)
      if (friend) {
        friend.status = online ? 1 : 0
      }
    }
  }
})
