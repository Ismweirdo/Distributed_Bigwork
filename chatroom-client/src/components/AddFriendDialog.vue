<template>
  <el-dialog v-model="visible" title="添加好友" width="450px" @open="onOpen">
    <el-input v-model="keyword" placeholder="搜索用户名或昵称" prefix-icon="Search" size="large"
      @keyup.enter="handleSearch" />
    <div style="margin-top: 16px;">
      <div v-if="searching" style="text-align:center;padding:20px;color:#999;">搜索中...</div>
      <div v-else-if="results.length > 0">
        <div v-for="user in results" :key="user.id" class="search-result-item">
          <div class="result-info">
            <el-avatar :size="36">{{ (user.nickname || user.username)[0] }}</el-avatar>
            <div>
              <div>{{ user.nickname || user.username }}</div>
              <div style="font-size:12px;color:#999;">@{{ user.username }}</div>
            </div>
          </div>
          <el-button type="primary" size="small" @click="addFriend(user.id)" :loading="adding === user.id">
            添加
          </el-button>
        </div>
      </div>
      <div v-else-if="searched" style="text-align:center;padding:20px;color:#999;">未找到匹配的用户</div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { searchUsers, sendFriendRequest } from '../api/friend'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean
})
const emit = defineEmits(['update:visible', 'done'])

const visible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const keyword = ref('')
const results = ref([])
const searching = ref(false)
const searched = ref(false)
const adding = ref(null)

function onOpen() {
  keyword.value = ''
  results.value = []
  searched.value = false
}

async function handleSearch() {
  if (!keyword.value.trim()) return
  searching.value = true
  searched.value = false
  try {
    results.value = await searchUsers(keyword.value.trim())
    searched.value = true
  } catch (e) {
    // Handled by interceptor
  } finally {
    searching.value = false
  }
}

async function addFriend(userId) {
  adding.value = userId
  try {
    await sendFriendRequest({ friendId: userId })
    ElMessage.success('好友申请已发送')
    visible.value = false
    emit('done')
  } catch (e) {
    // Handled by interceptor
  } finally {
    adding.value = null
  }
}
</script>

<style scoped>
.search-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}
.result-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
