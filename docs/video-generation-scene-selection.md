# 场景分镜场景选择功能方案

## 📋 需求说明

**当前界面：**
```text
场景分镜
[上传文件] [粘贴文字]
┌───────────────────────┐
│ 文本输入框            │
└───────────────────────┘
[开始解析分镜]
```

**目标界面：**
- 参照 Step4 的剧本展示样式（卡片式）
- 每个场景可勾选
- 支持章节级别的批量选择
- 保留手动输入功能

---

## 🎨 UI 设计（参照 Step4）

### 界面预览

```text
┌─────────────────────────────────────────────────────────┐
│  场景分镜                                                │
│  选择场景进行分镜解析和视频生成                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📖 从 Step4 导入的剧本                                  │
│  已选择 2/5 个场景        [全选] [清空] [手动输入]      │
│                                                          │
│  ┌────────────────────────────────────────────┐        │
│  │ 第 1 集 相遇                        [✓]   │        │
│  ├────────────────────────────────────────────┤        │
│  │ ☑ 场景 01                                   │        │
│  │   环境：温馨的咖啡馆                        │        │
│  │   画面：小明走进咖啡馆，环顾四周            │        │
│  │   小明：你好，请问这里有人吗？              │        │
│  │                                             │        │
│  │ ☑ 场景 02                                   │        │
│  │   环境：傍晚的街道                          │        │
│  │   画面：两人并肩走在街上                    │        │
│  │                                             │        │
│  │ ☐ 场景 03                                   │        │
│  │   环境：夜晚的公园                          │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
│  ┌────────────────────────────────────────────┐        │
│  │ 第 2 集 误会                        [ ]   │        │
│  ├────────────────────────────────────────────┤        │
│  │ ☐ 场景 01                                   │        │
│  │   环境：现代办公室                          │        │
│  │                                             │        │
│  │ ☐ 场景 02                                   │        │
│  │   环境：高档西餐厅                          │        │
│  └────────────────────────────────────────────┘        │
│                                                          │
│  Provider: [Claude ▼]  Model: [claude-sonnet ▼]        │
│  [开始解析分镜]                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 💻 代码实现

### 1. Template 结构

```vue
<template>
  <div class="page">
    <StepIndicator :current="5" />
    <div class="content">
      <h1>场景分镜</h1>
      <p class="subtitle">选择场景进行分镜解析和视频生成</p>

      <!-- 从 Step4 导入的剧本 -->
      <div v-if="hasStoryData" class="story-import">
        <!-- 标题栏 -->
        <div class="import-header">
          <div class="header-left">
            <span class="import-icon">📖</span>
            <h3>从 Step4 导入的剧本</h3>
          </div>
          <div class="header-right">
            <span class="scene-count">已选择 {{ selectedCount }}/{{ totalScenes }} 个场景</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="import-actions">
          <button class="action-btn" @click="selectAll">
            <span>✓</span> 全选
          </button>
          <button class="action-btn" @click="clearSelection">
            <span>✕</span> 清空
          </button>
          <button class="action-btn" @click="showManualInput = true">
            <span>✎</span> 手动输入
          </button>
        </div>

        <!-- 场景卡片列表（参照 SceneStream 样式） -->
        <div class="episode-list">
          <div v-for="ep in storyStore.scenes" :key="ep.episode" class="episode-card">
            <!-- 集标题（参照 SceneStream） -->
            <div class="ep-header" @click="toggleEpisode(ep.episode)">
              <input
                type="checkbox"
                :checked="isEpisodeSelected(ep.episode)"
                :indeterminate.prop="isEpisodeIndeterminate(ep.episode)"
                @click.stop
                @change="toggleEpisode(ep.episode)"
                class="ep-checkbox"
              />
              <span class="ep-badge">第 {{ ep.episode }} 集</span>
              <span class="ep-title">{{ ep.title }}</span>
              <span class="ep-count">{{ getEpisodeSelectedCount(ep.episode) }}/{{ ep.scenes.length }}</span>
            </div>

            <!-- 场景列表 -->
            <div class="scenes">
              <div
                v-for="scene in ep.scenes"
                :key="scene.scene_number"
                class="scene-block"
                :class="{ selected: selectedScenes[ep.episode]?.[scene.scene_number] }"
              >
                <!-- 场景标题和复选框 -->
                <div class="scene-header" @click="toggleScene(ep.episode, scene.scene_number)">
                  <input
                    type="checkbox"
                    v-model="selectedScenes[ep.episode][scene.scene_number]"
                    @click.stop
                    class="scene-checkbox"
                  />
                  <span class="scene-num">场景 {{ String(scene.scene_number).padStart(2, '0') }}</span>
                </div>

                <!-- 场景内容（参照 SceneStream） -->
                <div class="scene-content">
                  <div class="scene-row">
                    <span class="scene-tag">【环境】</span>
                    <span class="scene-text">{{ scene.environment }}</span>
                  </div>
                  <div class="scene-row">
                    <span class="scene-tag">【画面】</span>
                    <span class="scene-text">{{ scene.visual }}</span>
                  </div>

                  <!-- 台词 -->
                  <div v-if="scene.audio && scene.audio.length > 0" class="audio-lines">
                    <div v-for="(a, i) in scene.audio" :key="i" class="audio-line">
                      <span class="character">{{ a.character }}：</span>
                      <span class="line">{{ a.line }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态：无剧本数据 -->
      <div v-else class="empty-state">
        <div class="empty-icon">📝</div>
        <p class="empty-title">没有检测到剧本数据</p>
        <p class="empty-desc">请先在 Step4 生成剧本，或手动输入剧本内容</p>
        <div class="empty-actions">
          <button class="primary-btn" @click="router.push('/step4')">
            前往 Step4
          </button>
          <button class="secondary-btn" @click="showManualInput = true">
            手动输入
          </button>
        </div>
      </div>

      <!-- 手动输入模态框 -->
      <div v-if="showManualInput" class="modal-overlay" @click.self="showManualInput = false">
        <div class="modal">
          <div class="modal-header">
            <h3>手动输入剧本</h3>
            <button class="close-btn" @click="showManualInput = false">✕</button>
          </div>

          <div class="modal-body">
            <div class="tabs">
              <button class="tab-btn" :class="{ active: manualTab === 'upload' }" @click="manualTab = 'upload'">
                上传文件
              </button>
              <button class="tab-btn" :class="{ active: manualTab === 'paste' }" @click="manualTab = 'paste'">
                粘贴文字
              </button>
            </div>

            <div v-show="manualTab === 'upload'" class="upload-zone">
              <!-- 上传区域 -->
            </div>

            <div v-show="manualTab === 'paste'">
              <textarea v-model="manualScript" class="script-textarea" placeholder="粘贴剧本内容..."></textarea>
            </div>
          </div>

          <div class="modal-footer">
            <button class="cancel-btn" @click="showManualInput = false">取消</button>
            <button class="confirm-btn" @click="confirmManualInput">确定</button>
          </div>
        </div>
      </div>

      <!-- Controls -->
      <div class="controls">
        <select v-model="selectedProvider" @change="updateModels">
          <option value="">选择 Provider</option>
          <option value="claude">Claude</option>
          <!-- ... -->
        </select>
        <select v-model="selectedModel">
          <option value="">选择模型</option>
          <!-- ... -->
        </select>
        <button @click="parseStoryboard" :disabled="isParsing || selectedCount === 0">
          {{ isParsing ? '解析中...' : `开始解析 ${selectedCount} 个场景` }}
        </button>
      </div>

      <!-- Progress、Error、Storyboard 等保持不变 -->
    </div>
  </div>
</template>
```

### 2. Script 逻辑

```javascript
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSettingsStore } from '../stores/settings.js'
import { useStoryStore } from '../stores/story.js'
import StepIndicator from '../components/StepIndicator.vue'
import ApiKeyModal from '../components/ApiKeyModal.vue'

const router = useRouter()
const settings = useSettingsStore()
const storyStore = useStoryStore()

// 场景选择相关
const selectedScenes = ref({})
const showManualInput = ref(false)
const manualTab = ref('paste')
const manualScript = ref('')

// Provider/Model 相关
const selectedProvider = ref('')
const selectedModel = ref('')
const availableModels = ref([])
const isParsing = ref(false)
const error = ref('')
const shots = ref([])
const voices = ref([])
const selectedVoice = ref('')
const showKeyModal = ref(false)
const keyModalType = ref('missing')
const keyModalMsg = ref('')
const progress = ref({ show: false, label: '', percent: 0 })

const MODELS = {
  claude: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  qwen: ['qwen-plus', 'qwen-max', 'qwen-turbo'],
  zhipu: ['glm-4', 'glm-4-flash', 'glm-3-turbo'],
  gemini: ['gemini-2.0-flash', 'gemini-2.0-pro', 'gemini-1.5-flash'],
}

// 计算属性
const hasStoryData = computed(() => {
  return storyStore.scenes && storyStore.scenes.length > 0
})

const selectedCount = computed(() => {
  let count = 0
  Object.values(selectedScenes.value).forEach(episode => {
    Object.values(episode).forEach(selected => {
      if (selected) count++
    })
  })
  return count
})

const totalScenes = computed(() => {
  if (!storyStore.scenes) return 0
  return storyStore.scenes.reduce((sum, ep) => sum + ep.scenes.length, 0)
})

// 场景选择相关函数
function initSelectedScenes() {
  storyStore.scenes.forEach(episode => {
    if (!selectedScenes.value[episode.episode]) {
      selectedScenes.value[episode.episode] = {}
    }
    episode.scenes.forEach(scene => {
      if (selectedScenes.value[episode.episode][scene.scene_number] === undefined) {
        selectedScenes.value[episode.episode][scene.scene_number] = false
      }
    })
  })
}

function toggleScene(episodeNum, sceneNum) {
  selectedScenes.value[episodeNum][sceneNum] = !selectedScenes.value[episodeNum][sceneNum]
}

function toggleEpisode(episodeNum) {
  const allSelected = isEpisodeSelected(episodeNum)
  const episode = selectedScenes.value[episodeNum]

  Object.keys(episode).forEach(sceneNum => {
    episode[sceneNum] = !allSelected
  })
}

function isEpisodeSelected(episodeNum) {
  const episode = selectedScenes.value[episodeNum]
  if (!episode) return false
  return Object.values(episode).every(v => v === true)
}

function isEpisodeIndeterminate(episodeNum) {
  const episode = selectedScenes.value[episodeNum]
  if (!episode) return false
  const values = Object.values(episode)
  const selected = values.filter(v => v).length
  return selected > 0 && selected < values.length
}

function getEpisodeSelectedCount(episodeNum) {
  const episode = selectedScenes.value[episodeNum]
  if (!episode) return 0
  return Object.values(episode).filter(v => v).length
}

function selectAll() {
  storyStore.scenes.forEach(episode => {
    episode.scenes.forEach(scene => {
      selectedScenes.value[episode.episode][scene.scene_number] = true
    })
  })
}

function clearSelection() {
  storyStore.scenes.forEach(episode => {
    episode.scenes.forEach(scene => {
      selectedScenes.value[episode.episode][scene.scene_number] = false
    })
  })
}

function confirmManualInput() {
  showManualInput.value = false
  // 使用 manualScript.value
}

function getScript() {
  if (hasStoryData.value) {
    return generateScriptFromSelection()
  } else if (manualScript.value) {
    return manualScript.value.trim()
  }
  return ''
}

function generateScriptFromSelection() {
  const parts = []

  storyStore.scenes.forEach(episode => {
    const selectedInEpisode = episode.scenes.filter(scene =>
      selectedScenes.value[episode.episode]?.[scene.scene_number]
    )

    if (selectedInEpisode.length > 0) {
      parts.push(`第 ${episode.episode} 集：${episode.title}\n`)

      selectedInEpisode.forEach(scene => {
        parts.push(`\n【场景 ${scene.scene_number}】`)
        parts.push(`环境：${scene.environment}`)
        parts.push(`画面：${scene.visual}`)

        if (scene.audio && scene.audio.length > 0) {
          scene.audio.forEach(a => {
            parts.push(`${a.character}：${a.line}`)
          })
        }
        parts.push('')
      })
    }
  })

  return parts.join('\n')
}

function isAuthError(msg) {
  return /401|403|invalid|incorrect|unauthorized|api.?key/i.test(msg)
}

async function parseStoryboard() {
  if (!settings.useMock && !settings.apiKey) {
    showKeyModal.value = true
    return
  }

  const script = getScript()

  if (!script) {
    error.value = '请先选择场景或输入剧本内容'
    return
  }
  if (!selectedProvider.value) {
    error.value = '请选择 Provider'
    return
  }

  isParsing.value = true
  error.value = ''
  shots.value = []
  progress.value = { show: true, label: '正在调用 LLM 解析分镜...', percent: 20 }

  try {
    const projectId = 'ui-' + Date.now()
    const params = new URLSearchParams({ script, provider: selectedProvider.value })
    if (selectedModel.value) params.append('model', selectedModel.value)

    progress.value = { show: true, label: 'LLM 处理中，请稍候...', percent: 60 }

    const res = await fetch(`${getBackendUrl()}/api/v1/pipeline/${projectId}/storyboard?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getHeaders()
      }
    })

    if (!res.ok) {
      const errData = await res.json()
      throw new Error(errData.detail || '请求失败')
    }

    progress.value = { show: true, label: '解析完成，渲染卡片...', percent: 90 }
    const data = await res.json()
    shots.value = data.shots.map(s => ({ ...s, ttsLoading: false, imageLoading: false, videoLoading: false }))
    progress.value = { show: true, label: '完成', percent: 100 }

    setTimeout(() => {
      progress.value.show = false
    }, 800)
  } catch (err) {
    const msg = err.message || '请求失败'
    if (isAuthError(msg)) {
      keyModalType.value = 'invalid'
      keyModalMsg.value = 'API Key 无效或已过期，请检查后重新设置。'
      showKeyModal.value = true
    } else {
      error.value = '错误：' + msg
    }
    progress.value.show = false
  } finally {
    isParsing.value = false
  }
}

function getBackendUrl() {
  return settings.backendUrl || 'http://localhost:8000'
}

function getHeaders() {
  const headers = {}
  if (settings.apiKey) headers['X-LLM-API-Key'] = settings.apiKey
  if (settings.llmBaseUrl) headers['X-LLM-Base-URL'] = settings.llmBaseUrl
  if (settings.provider) headers['X-LLM-Provider'] = settings.provider
  return headers
}

function updateModels() {
  availableModels.value = []
  if (selectedProvider.value && MODELS[selectedProvider.value]) {
    availableModels.value = MODELS[selectedProvider.value]
    selectedModel.value = MODELS[selectedProvider.value][0]
  }
}

// TTS/Image/Video 生成函数保持不变...

onMounted(() => {
  loadVoices()

  if (hasStoryData.value) {
    initSelectedScenes()
    // 可选：默认选中第一个场景
    const firstEpisode = storyStore.scenes[0]
    if (firstEpisode && firstEpisode.scenes.length > 0) {
      selectedScenes.value[firstEpisode.episode][firstEpisode.scenes[0].scene_number] = true
    }
  }
})
</script>
```

### 3. 样式（基于 SceneStream 扩展）

```css
<style scoped>
/* 基础样式保持不变... */

/* 导入区域 */
.story-import {
  max-width: 900px;
  margin: 0 auto;
}

.import-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0eeff 0%, #fff 100%);
  border: 1px solid #e0e0e0;
  border-bottom: none;
  border-radius: 12px 12px 0 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.import-icon {
  font-size: 20px;
}

.import-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
}

.scene-count {
  font-size: 13px;
  color: #6c63ff;
  font-weight: 600;
  background: #fff;
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid #d0d0ff;
}

.import-actions {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-bottom: none;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #fff;
  color: #666;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: #6c63ff;
  color: #6c63ff;
  background: #f0eeff;
}

/* 场景列表（参照 SceneStream） */
.episode-list {
  border: 1px solid #e0e0e0;
  border-radius: 0 0 12px 12px;
  overflow: hidden;
}

.episode-card {
  border-bottom: 1px solid #e0e0e0;
}

.episode-card:last-child {
  border-bottom: none;
}

.ep-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #f8f8f8;
  cursor: pointer;
  transition: background 0.2s;
  user-select: none;
}

.ep-header:hover {
  background: #f0f0f0;
}

.ep-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.ep-badge {
  background: #6c63ff;
  color: #fff;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.ep-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.ep-count {
  font-size: 12px;
  color: #999;
  background: #fff;
  padding: 2px 8px;
  border-radius: 10px;
}

.scenes {
  padding: 0;
}

.scene-block {
  border-top: 1px solid #f0f0f0;
  transition: background 0.2s;
}

.scene-block.selected {
  background: #f0eeff;
}

.scene-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  cursor: pointer;
  transition: background 0.2s;
}

.scene-header:hover {
  background: #fafafa;
}

.scene-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.scene-num {
  color: #6c63ff;
  font-weight: 600;
  font-size: 13px;
}

.scene-content {
  padding: 0 16px 12px 42px;
}

.scene-row {
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.scene-tag {
  color: #999;
  font-weight: 600;
}

.scene-text {
  color: #333;
}

.audio-lines {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 6px;
  border-left: 3px solid #6c63ff;
}

.audio-line {
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 4px;
}

.character {
  color: #6c63ff;
  font-weight: 600;
}

.line {
  color: #555;
}

/* 空状态 */
.empty-state {
  max-width: 600px;
  margin: 60px auto;
  padding: 48px 32px;
  text-align: center;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #999;
  margin-bottom: 24px;
}

.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.primary-btn,
.secondary-btn {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.primary-btn {
  background: #6c63ff;
  color: #fff;
  border: none;
}

.primary-btn:hover {
  background: #5a52e0;
}

.secondary-btn {
  background: #fff;
  color: #666;
  border: 1px solid #e0e0e0;
}

.secondary-btn:hover {
  border-color: #6c63ff;
  color: #6c63ff;
}

/* 模态框样式保持不变... */

/* Controls 样式保持不变... */
</style>
```

---

## 📝 实现步骤

1. **删除旧的 Tab 系统**
   - 移除 `activeTab` 变量和相关的 `[上传文件] [粘贴文字]` 按钮
   - 移除 `input-panel` 相关的 template 和样式

2. **添加场景选择组件**
   - 添加 `story-import` 卡片区域
   - 实现集-场景的树形展示（参照 SceneStream）

3. **实现选择逻辑**
   - 添加 `selectedScenes` 等响应式变量
   - 实现 `toggleScene`, `toggleEpisode` 等函数
   - 实现 `selectAll`, `clearSelection` 快捷操作

4. **修改 getScript 函数**
   - 实现 `generateScriptFromSelection()`
   - 根据选中的场景动态生成剧本文本

5. **添加空状态和手动输入**
   - 无剧本时显示空状态提示
   - 点击"手动输入"显示模态框

6. **调整样式**
   - 基于 SceneStream 样式扩展
   - 添加选中状态的视觉反馈
   - 保持与整体风格一致

---

## ✅ 优势

1. **与 Step4 风格统一** - 使用相同的卡片式布局
2. **直观易用** - 复选框交互简单明了
3. **灵活选择** - 支持场景级别和集级别的批量操作
4. **实时反馈** - 选中数量实时更新
5. **向后兼容** - 保留手动输入功能

---

## ⚠️ 注意事项

- 确保从 Step4 跳转时 store 数据已加载
- 处理浏览器刷新后 store 丢失的情况
- 未选择任何场景时禁用"开始解析"按钮
- 保持样式与 Step1-4 完全一致
