<template>
  <div class="chat-window">
    <!-- Header -->
    <div class="chat-header">
      <div class="chat-header-info">
        <span class="chat-title">{{ targetName }}</span>
        <span v-if="type === 'group'" class="chat-subtitle">群聊</span>
      </div>
    </div>

    <!-- Messages -->
    <div class="chat-messages" ref="msgContainer">
      <div v-if="loading" class="loading-hint">加载中...</div>
      <div v-for="msg in chatStore.currentMessages" :key="msg.id || msg.clientMessageId">
        <MessageBubble :message="msg" :isMine="msg.senderId === userStore.userId"
          @reply="onReplyMessage(msg)" @recall="onRecallMessage(msg)" />
      </div>
      <div ref="msgEnd"></div>
    </div>

    <!-- Reply bar -->
    <div v-if="replyingTo" class="reply-bar">
      <span>回复 {{ replyingTo.senderName }}: {{ truncate(replyingTo.content, 50) }}</span>
      <el-button text @click="replyingTo = null"><el-icon><Close /></el-icon></el-button>
    </div>

    <!-- Input -->
    <div class="chat-input">
      <el-input v-model="input" type="textarea" :rows="3" placeholder="输入消息..."
        @keyup.enter.exact="sendMessage" resize="none" />
      <el-button type="primary" @click="sendMessage" :disabled="!input.trim()">发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { useUserStore } from '../store/user'
import { useChatStore } from '../store/chat'
import { sendChatMessage, subscribeGroupMessages, unsubscribeGroupMessages } from '../utils/websocket'
import { recallMessage } from '../api/message'
import { ElMessage } from 'element-plus'
import MessageBubble from './MessageBubble.vue'

const props = defineProps({
  type: { type: String, required: true },
  targetId: { type: Number, required: true },
  targetName: { type: String, required: true }
})

const userStore = useUserStore()
const chatStore = useChatStore()
const input = ref('')
const replyingTo = ref(null)
const msgContainer = ref(null)
const msgEnd = ref(null)
const loading = ref(false)

const chatKey = computed(() => `${props.type}_${props.targetId}`)

async function loadHistory() {
  chatStore.setCurrentChat(chatKey.value)
  loading.value = true
  try {
    await chatStore.fetchHistory(props.type, props.targetId)
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

onMounted(() => {
  loadHistory()
  if (props.type === 'group') {
    subscribeGroupMessages(props.targetId)
  }
})

onUnmounted(() => {
  if (props.type === 'group') {
    unsubscribeGroupMessages(props.targetId)
  }
})

// Watch for target changes (switching contacts)
watch(() => props.targetId, () => {
  loadHistory()
  if (props.type === 'group') {
    subscribeGroupMessages(props.targetId)
  }
})

// Auto-scroll on new messages
watch(() => chatStore.currentMessages.length, () => {
  nextTick(() => scrollToBottom())
})

function sendMessage() {
  if (!input.value.trim()) return

  const dto = {
    content: input.value.trim(),
    messageType: props.type === 'private' ? 0 : 1,
    targetId: props.targetId,
    replyToId: replyingTo.value?.id || null,
    contentType: 0,
    clientMessageId: generateUUID()
  }

  const sent = sendChatMessage(dto)
  if (sent) {
    input.value = ''
    replyingTo.value = null
  } else {
    ElMessage.error('连接已断开，请刷新页面')
  }
}

function onReplyMessage(msg) {
  replyingTo.value = msg
}

async function onRecallMessage(msg) {
  try {
    await recallMessage(msg.id)
    chatStore.updateMessage(chatKey.value, msg.id, { content: '[消息已撤回]' })
  } catch (e) {
    // Handled by interceptor
  }
}

function scrollToBottom() {
  nextTick(() => {
    msgEnd.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.substring(0, len) + '...' : text
}

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}
</script>

<style scoped>
.chat-window { display: flex; flex-direction: column; height: 100%; }
.chat-header { padding: 16px 20px; background: #fff; border-bottom: 1px solid #e0e0e0; }
.chat-header-info { display: flex; align-items: center; gap: 8px; }
.chat-title { font-size: 18px; font-weight: 600; }
.chat-subtitle { font-size: 12px; color: #999; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px 20px; background: #fafafa; }
.reply-bar { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px; background: #f0f0f0; font-size: 13px; color: #666; border-top: 1px solid #e0e0e0; }
.chat-input { display: flex; padding: 12px 16px; background: #fff; border-top: 1px solid #e0e0e0; gap: 12px; align-items: flex-end; }
.chat-input :deep(.el-textarea__inner) { resize: none; }
.loading-hint { text-align: center; color: #999; padding: 20px; }
</style>
