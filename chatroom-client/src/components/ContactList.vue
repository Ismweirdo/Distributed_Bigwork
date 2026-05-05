<template>
  <div class="contact-list">
    <!-- Search -->
    <div class="search-box">
      <el-input v-model="search" placeholder="搜索" prefix-icon="Search" size="small" clearable />
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="contact-tabs">
      <el-tab-pane label="好友" name="friends">
        <div v-if="contactStore.friendList.length === 0" class="empty-hint">暂无好友，点击 + 添加好友</div>
        <div v-for="friend in filteredFriends" :key="friend.friendId"
          class="contact-item" :class="{ active: isActive('private', friend.friendId) }"
          @click="selectContact('private', friend.friendId, friend.nickname || friend.username)">
          <el-badge :is-dot="friend.status === 1" class="avatar-badge" type="success" :offset="[0, 36]">
            <el-avatar :size="40">{{ (friend.nickname || friend.username)[0] }}</el-avatar>
          </el-badge>
          <div class="contact-info">
            <div class="contact-name">{{ friend.nickname || friend.username }}</div>
            <div class="contact-status">{{ friend.status === 1 ? '在线' : '离线' }}</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="群聊" name="groups">
        <div v-if="filteredGroups.length === 0 && !search" class="empty-hint">暂无群聊，点击消息图标创建群</div>
        <div v-for="group in filteredGroups" :key="group.id"
          class="contact-item" :class="{ active: isActive('group', group.id) }"
          @click="selectContact('group', group.id, group.name)"
          @dblclick="emit('groupInfo', group)">
          <el-avatar :size="40">{{ group.name[0] }}</el-avatar>
          <div class="contact-info">
            <div class="contact-name">{{ group.name }}</div>
            <div class="contact-status">{{ group.memberCount }} 人</div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useContactStore } from '../store/contact'

const emit = defineEmits(['select', 'groupInfo'])
const contactStore = useContactStore()
const search = ref('')
const activeTab = ref('friends')

const filteredFriends = computed(() => {
  if (!search.value) return contactStore.friendList
  const kw = search.value.toLowerCase()
  return contactStore.friendList.filter(f =>
    (f.nickname || f.username).toLowerCase().includes(kw)
  )
})

const filteredGroups = computed(() => {
  if (!search.value) return contactStore.groupList
  const kw = search.value.toLowerCase()
  return contactStore.groupList.filter(g => g.name.toLowerCase().includes(kw))
})

function isActive(type, id) {
  const contact = contactStore.activeContact
  return contact && contact.type === type && contact.id === id
}

function selectContact(type, id, name) {
  const contact = { type, id, name, key: `${type}_${id}` }
  contactStore.setActiveContact(contact)
  emit('select', contact)
}
</script>

<style scoped>
.contact-list {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.search-box {
  padding: 12px 16px;
}
.contact-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.contact-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
}
.contact-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  gap: 12px;
  transition: background 0.2s;
}
.contact-item:hover {
  background: #e8e8e8;
}
.contact-item.active {
  background: #d9ecff;
}
.contact-info {
  flex: 1;
  min-width: 0;
}
.contact-name {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.contact-status {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}
.avatar-badge {
  flex-shrink: 0;
}
.empty-hint {
  text-align: center;
  color: #bbb;
  padding: 40px 16px;
  font-size: 14px;
}
</style>
