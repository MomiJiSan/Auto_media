<template>
  <!-- 遮罩 -->
  <div v-if="show" class="overlay" @click="$emit('close')" />

  <!-- 侧边面板 -->
  <div class="panel" :class="{ open: show }">
    <div class="panel-header">
      <span>剧情 AI 修改助手</span>
      <button class="close-btn" @click="$emit('close')">✕</button>
    </div>

    <div v-if="episode" class="episode-info">
      <div class="ep-num">第 {{ episode.episode }} 集</div>
      <div class="ep-title">{{ episode.title }}</div>
    </div>

    <div class="chat-history" ref="historyEl">
      <div v-if="messages.length === 0" class="empty-hint">
        告诉我你想怎么修改这一集，比如：<br>「加入一个意外转折」
      </div>
      <div v-for="(msg, i) in messages" :key="i" :class="['bubble', msg.role]">
        <div class="bubble-text" v-html="msg.text.replace(/\n/g, '<br>')" />
        <button
          v-if="msg.role === 'ai' && msg.refine"
          class="apply-btn"
          :disabled="msg.applied"
          @click="applyRefine(msg)"
        >
          {{ msg.applied ? '已应用 ✓' : '应用修改' }}
        </button>
      </div>
      <div v-if="streaming" class="bubble ai">
        <div class="bubble-text streaming">{{ streamingText }}<span class="cursor">|</span></div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        placeholder="描述你想修改的内容..."
        rows="3"
        @keydown.enter.exact.prevent="send"
      />
      <button class="send-btn" :disabled="!input.trim() || streaming" @click="send">
        {{ streaming ? '思考中...' : '发送' }}
      </button>
    </div>
    <div v-if="error" class="error-tip">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useStoryStore } from '../stores/story.js'
import { streamChat, refineStory } from '../api/story.js'

const props = defineProps({
  show: Boolean,
  episode: Object
})
defineEmits(['close'])

const store = useStoryStore()
const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamingText = ref('')
const error = ref('')
const historyEl = ref(null)

async function scrollToBottom() {
  await nextTick()
  if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
}

watch(() => messages.value.length, scrollToBottom)
watch(streamingText, scrollToBottom)

// 清空消息当集数改变时
watch(() => props.episode?.episode, () => {
  messages.value = []
  input.value = ''
  error.value = ''
})

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value || !props.episode) return
  input.value = ''
  error.value = ''

  messages.value = [...messages.value, { role: 'user', text }]

  // 构造集数上下文
  const epCtx = JSON.stringify({
    episode: props.episode.episode,
    title: props.episode.title,
    summary: props.episode.summary,
  }, null, 2)

  const fullMessage = `当前剧集信息：\n${epCtx}\n\n用户要求：${text}\n\n请理解用户意图，给出具体的修改建议（说明标题和剧情改成什么），并在回复末尾用 JSON 块标注修改内容，格式：\n\`\`\`refine\n{"change_type":"episode","change_summary":"..."}\n\`\`\``

  streaming.value = true
  streamingText.value = ''

  await streamChat(
    store.storyId,
    fullMessage,
    (chunk) => { streamingText.value += chunk },
    () => {
      streaming.value = false
      const fullText = streamingText.value
      streamingText.value = ''

      // 尝试提取 refine JSON
      const refineMatch = fullText.match(/```refine\s*([\s\S]*?)```/)
      let refineData = null
      let displayText = fullText
      if (refineMatch) {
        try {
          refineData = JSON.parse(refineMatch[1].trim())
          displayText = fullText.replace(/```refine[\s\S]*?```/, '').trim()
        } catch {}
      }

      messages.value = [...messages.value, {
        role: 'ai',
        text: displayText,
        refine: refineData,
        applied: false,
      }]
    },
    (msg) => {
      streaming.value = false
      streamingText.value = ''
      error.value = msg || 'AI 响应失败，请重试'
    }
  )
}

async function applyRefine(msg) {
  if (!msg.refine) return
  try {
    const res = await refineStory(store.storyId, msg.refine.change_type, msg.refine.change_summary)
    if (res) store.applyRefine(res)
    // 标记已应用（不可变更新）
    messages.value = messages.value.map(m =>
      m === msg ? { ...m, applied: true } : m
    )
  } catch {
    error.value = '应用失败，请重试'
  }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.2);
  z-index: 100;
}

.panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 360px;
  height: 100vh;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0,0,0,0.12);
  z-index: 101;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.3s ease;
}
.panel.open { transform: translateX(0); }

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.close-btn {
  background: none;
  border: none;
  font-size: 16px;
  color: #aaa;
  cursor: pointer;
  padding: 4px;
}
.close-btn:hover { color: #555; }

.episode-info {
  padding: 12px 16px;
  background: #f0eeff;
  border-bottom: 1px solid #e0d9ff;
}
.ep-num {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
.ep-title {
  font-size: 14px;
  font-weight: 600;
  color: #6c63ff;
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty-hint {
  color: #bbb;
  font-size: 13px;
  line-height: 1.8;
  text-align: center;
  margin-top: 40px;
}

.bubble { max-width: 90%; display: flex; flex-direction: column; gap: 6px; }
.bubble.user { align-self: flex-end; }
.bubble.ai { align-self: flex-start; }
.bubble-text {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.6;
}
.bubble.user .bubble-text { background: #6c63ff; color: #fff; border-bottom-right-radius: 4px; }
.bubble.ai .bubble-text { background: #f5f5f7; color: #333; border-bottom-left-radius: 4px; }
.streaming { color: #888; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: 0 } }

.apply-btn {
  align-self: flex-start;
  padding: 6px 14px;
  background: #6c63ff;
  color: #fff;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.apply-btn:hover:not(:disabled) { opacity: 0.85; }
.apply-btn:disabled { background: #aaa; cursor: default; }

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: 10px;
  border: 2px solid #e0e0e0;
  font-size: 13px;
  resize: none;
  line-height: 1.6;
  font-family: inherit;
  transition: border-color 0.2s;
}
textarea:focus { border-color: #6c63ff; outline: none; }
.send-btn {
  padding: 10px;
  background: #6c63ff;
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.send-btn:hover:not(:disabled) { background: #5a52e0; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error-tip { padding: 0 16px 12px; color: #e53935; font-size: 12px; }
</style>
