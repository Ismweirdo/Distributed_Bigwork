<template>
  <div class="message-wrapper" :class="{ mine: isMine }">
    <div class="message-avatar" v-if="!isMine">
      <el-avatar :size="32">{{ (message.senderName || '?')[0] }}</el-avatar>
    </div>
    <div class="message-body">
      <div class="message-sender" v-if="!isMine">{{ message.senderName }}</div>
      <!-- Reply reference -->
      <div v-if="message.replyToId" class="reply-ref">
        <span class="reply-name">{{ message.replyToSenderName || '...' }}</span>
        <span class="reply-content">{{ truncate(message.replyToContent, 40) }}</span>
      </div>
      <div class="message-bubble">
        <div class="message-text">{{ message.content }}</div>
        <div class="message-time">{{ formatTime(message.createdAt) }}</div>
      </div>
      <!-- Actions on hover -->
      <div class="message-actions">
        <el-button text size="small" @click="$emit('reply', message)">回复</el-button>
        <el-button v-if="isMine && isRecalled(message)" text size="small" type="danger"
          @click="$emit('recall', message)">撤回</el-button>
      </div>
    </div>
    <div class="message-avatar" v-if="isMine">
      <el-avatar :size="32">{{ (message.senderName || '?')[0] }}</el-avatar>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  message: { type: Object, required: true },
  isMine: { type: Boolean, default: false }
})

defineEmits(['reply', 'recall'])

function formatTime(timeStr) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.substring(0, len) + '...' : text
}

function isRecalled(msg) {
  if (!msg.createdAt) return false
  const elapsed = Date.now() - new Date(msg.createdAt).getTime()
  return elapsed < 2 * 60 * 1000
}
</script>

<style scoped>
.message-wrapper {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.message-wrapper.mine {
  flex-direction: row-reverse;
}
.message-body {
  max-width: 60%;
}
.mine .message-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.message-sender {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
  margin-left: 4px;
}
.reply-ref {
  font-size: 12px;
  background: #f0f0f0;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 4px;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.reply-name {
  color: #667eea;
  margin-right: 4px;
}
.reply-content {
  color: #999;
}
.message-bubble {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  position: relative;
}
.mine .message-bubble {
  background: #a0cfff;
}
.message-text {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}
.message-time {
  font-size: 10px;
  color: #999;
  margin-top: 4px;
  text-align: right;
}
.message-actions {
  display: none;
  gap: 4px;
  margin-top: 2px;
}
.message-wrapper:hover .message-actions {
  display: flex;
}
</style>
