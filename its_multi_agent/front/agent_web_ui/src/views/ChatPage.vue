<template>
  <div class="app-container">
    <div v-if="!isLoggedIn" class="login-container">
      <div class="login-form">
        <div class="its-logo-flat login-logo">
          <img src="/its-logo.svg" alt="Multi-Agent Logo" width="60" height="60" />
        </div>
        <h1 class="login-title">售后多智能体系统登录</h1>
        <div class="login-input-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            @keyup.enter="handleLogin"
          />
        </div>
        <div class="login-input-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </div>
        <div v-if="loginError" class="login-error">{{ loginError }}</div>
        <button class="login-button btn-primary" @click="handleLogin">登录</button>
        <div class="login-hint">
          <p>测试用户：root1, root2, root3</p>
          <p>密码：123456</p>
        </div>
      </div>
    </div>

    <template v-else>
      <div class="main-content">
        <div class="sidebar-wrapper">
          <div class="sidebar-content" :class="{ expanded: isSidebarExpanded }">
            <div class="header-bar">
              <div class="header-logo">
                <img src="/its-logo.svg" alt="Logo" width="32" height="32" />
                <span class="header-title">智慧服务</span>
              </div>
              <button
                class="toggle-sidebar-btn"
                v-show="isSidebarExpanded"
                @click="toggleSidebar"
                :title="isSidebarExpanded ? '收起侧边栏' : '展开侧边栏'"
              >
                {{ isSidebarExpanded ? '‹' : '›' }}
              </button>
            </div>

            <div class="session-button-container" v-show="isSidebarExpanded">
              <a href="/" class="new-chat-btn" @click.prevent="createNewSession">
                <span class="icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 1024 1024">
                    <path d="M475.136 561.152v89.74336c0 20.56192 16.50688 37.23264 36.864 37.23264s36.864-16.67072 36.864-37.23264v-89.7024h89.7024c20.60288 0 37.2736-16.54784 37.2736-36.864 0-20.39808-16.67072-36.864-37.2736-36.864H548.864V397.63968A37.0688 37.0688 0 0 0 512 360.448c-20.35712 0-36.864 16.67072-36.864 37.2736v89.7024H385.4336a37.0688 37.0688 0 0 0-37.2736 36.864c0 20.35712 16.67072 36.864 37.2736 36.864h89.7024z" fill="currentColor" />
                    <path d="M512 118.784c-223.96928 0-405.504 181.57568-405.504 405.504 0 78.76608 22.44608 152.3712 61.35808 214.6304l-44.27776 105.6768a61.44 61.44 0 0 0 56.68864 85.1968H512c223.92832 0 405.504-181.53472 405.504-405.504 0-223.92832-181.57568-405.504-405.504-405.504z m-331.776 405.504a331.776 331.776 0 1 1 331.73504 331.776H198.656l52.59264-125.5424-11.59168-16.62976A330.09664 330.09664 0 0 1 180.224 524.288z" fill="currentColor" />
                  </svg>
                </span>
                <span class="text">新建会话</span>
                <span class="shortcut">
                  <span class="key">Ctrl</span>
                  <span>+</span>
                  <span class="key">K</span>
                </span>
              </a>
            </div>

            <div class="history-section">
              <div class="history-header" @click="toggleSessions">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 1024 1024" class="nav-icon">
                  <path d="M512 81.066667c-233.301333 0-422.4 189.098667-422.4 422.4s189.098667 422.4 422.4 422.4 422.4-189.098667 422.4-422.4-189.098667-422.4-422.4-422.4z m-345.6 422.4a345.6 345.6 0 1 1 691.2 0 345.6 345.6 0 1 1-691.2 0z m379.733333-174.933334a38.4 38.4 0 0 0-76.8 0v187.733334a38.4 38.4 0 0 0 11.264 27.136l93.866667 93.866666a38.4 38.4 0 1 0 54.272-54.272L546.133333 500.352V328.533333z" fill="currentColor" />
                </svg>
                <span class="nav-text">历史会话</span>
              </div>
              <div v-show="showSessions" class="sessions-list">
                <div v-if="isLoadingSessions" class="loading-sessions">加载中...</div>
                <div v-else-if="sessions.length === 0" class="no-sessions">暂无记录</div>
                <div
                  v-for="session in sessions"
                  :key="session.session_id"
                  :class="['session-item', { selected: session.session_id === selectedSessionId }]"
                  @click="selectSession(session.session_id)"
                >
                  <img alt="会话" src="//lf-flow-web-cdn.doubao.com/obj/flow-doubao/doubao/chat/static/image/default.light.2ea4b2b4.png" class="session-icon" />
                  <div class="session-preview">{{ session.memory?.[0]?.content || '空对话' }}</div>
                </div>
              </div>
            </div>
          </div>
          <button
            v-if="!isSidebarExpanded"
            class="sidebar-reopen-btn"
            @click="toggleSidebar"
            title="展开侧边栏"
          >
            ›
          </button>
        </div>

        <div class="main-container">
          <div class="chat-container" :class="{ processing: isProcessing }">
            <div class="top-user-section">
              <div ref="avatarContainerRef" class="user-avatar-container">
                <img
                  src="https://p3-flow-imagex-sign.byteimg.com/user-avatar/assets/e7b19241fb224cea967dfaea35448102_1080_1080.png~tplv-a9rns2rl98-icon-tiny.png?rcl=202511070904143F9B891FA2E40D7123F0&rk3s=8e244e95&rrcfp=76e58463&x-expires=1765155855&x-signature=nqQBx1W9ABfrm%2FRKkEYZUzsYjE0%3D"
                  class="user-avatar"
                  alt="用户头像"
                  @click="toggleUserInfo"
                />
                <div v-show="showUserInfo" class="user-info-dropdown">
                  <template v-if="currentUser">
                    <span class="user-name">{{ currentUser }}</span>
                    <button class="btn-logout" @click="handleLogout">退出登录</button>
                  </template>
                  <template v-else>
                    <span class="user-name">当前未登录</span>
                    <button class="btn-primary" @click="goToLogin">请登录</button>
                  </template>
                </div>
              </div>
            </div>

            <div v-if="chatMessages.length === 0" class="welcome-area">
              <div class="welcome-icon">
                <img src="/its-logo.svg" alt="Logo" width="64" height="64" />
              </div>
              <h2 class="welcome-title">你好，我是联想智能售后客服</h2>
              <p class="welcome-subtitle">请问有什么可以帮您？</p>
            </div>

            <div class="chat-message-container">
              <div v-for="(msg, index) in chatMessages" :key="index" :class="['message-wrapper', msg.type]">
                <div v-if="msg.type === 'PROCESS_CARD'" class="message-content process-card-content">
                  <div class="agent-process-card">
                    <button class="agent-process-header" type="button" @click="toggleThinking(index)">
                      <div class="agent-process-title-wrap">
                        <span class="agent-process-status-dot" :class="msg.status"></span>
                        <span class="agent-process-title">
                          {{ msg.status === 'completed' ? '已完成' : msg.status === 'waiting_approval' ? '等待审批' : msg.status === 'cancelled' ? '已取消' : '正在处理' }}
                        </span>
                      </div>
                      <div class="agent-process-header-right">
                        <span class="agent-process-summary">{{ msg.summary || 'Agent 正在处理你的请求' }}</span>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          class="thinking-icon"
                          :class="{ collapsed: msg.collapsed }"
                        >
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </div>
                    </button>
                    <div v-show="!msg.collapsed" class="agent-process-body">
                      <div v-for="(step, stepIndex) in msg.steps" :key="`${step.key}-${stepIndex}`" class="agent-process-step">
                        <div class="agent-process-step-title">{{ step.label }}</div>
                        <div v-if="step.detail" class="agent-process-step-detail">{{ step.detail }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="msg.type === 'THINKING'" class="message-role-label" @click="toggleThinking(index)">
                  <div class="thinking-header">
                    <span class="thinking-text">
                      {{ isProcessing && index === chatMessages.length - 1 ? '思考中...' : '思考过程' }}
                    </span>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      class="thinking-icon"
                      :class="{ collapsed: msg.collapsed }"
                    >
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>
                </div>
                <div v-show="msg.type !== 'THINKING' || !msg.collapsed" class="message-content">
                  <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                  <div v-if="msg.type === 'assistant' && hasAssistantDiagnostics(msg)" class="assistant-diagnostics">
                    <div class="assistant-review-row">
                      <span
                        v-if="msg.reviewVerdict"
                        class="assistant-review-pill"
                        :class="`review-${msg.reviewVerdict.status || 'supported'}`"
                      >
                        {{ formatReviewStatus(msg.reviewVerdict.status) }}
                      </span>
                      <span v-if="msg.intent" class="assistant-review-pill review-neutral">
                        {{ formatIntentLabel(msg.intent) }}
                      </span>
                    </div>
                    <div v-if="msg.reviewVerdict?.summary" class="assistant-review-summary">
                      {{ msg.reviewVerdict.summary }}
                    </div>
                    <div v-if="msg.nextAction" class="assistant-next-action">
                      {{ msg.nextAction }}
                    </div>
                    <div v-if="msg.evidenceCards?.length" class="evidence-card-list">
                      <button
                        type="button"
                        class="evidence-toggle-btn"
                        @click="msg.evidenceExpanded = !msg.evidenceExpanded"
                      >
                        <span>回答依据</span>
                        <span class="evidence-toggle-meta">{{ msg.evidenceCards.length }} 条</span>
                        <span class="evidence-toggle-action">{{ msg.evidenceExpanded ? '收起' : '展开查看' }}</span>
                      </button>
                      <div v-show="msg.evidenceExpanded" class="evidence-card-stack">
                      <article
                        v-for="(card, cardIndex) in msg.evidenceCards"
                        :key="`${msg.content}-${card.title || 'evidence'}-${cardIndex}`"
                        class="evidence-card"
                      >
                        <div class="evidence-card-top">
                          <span
                            class="evidence-card-source"
                            :class="`source-${classifyEvidenceSource(card.source)}`"
                          >{{ formatEvidenceSource(card.source) }}</span>
                          <a
                            v-if="card.uri"
                            class="evidence-card-link"
                            :href="card.uri"
                            target="_blank"
                            rel="noreferrer"
                          >
                            查看来源
                          </a>
                        </div>
                        <div class="evidence-card-title">{{ card.title || formatEvidenceSource(card.source) }}</div>
                        <div v-if="card.snippet" class="evidence-card-snippet">{{ card.snippet }}</div>
                      </article>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="input-area">
              <div v-if="pendingApproval" class="approval-card">
                <div class="approval-title">{{ pendingApproval.title }}</div>
                <div class="approval-question">{{ pendingApproval.question }}</div>
                <div v-if="pendingApproval.details" class="approval-details">{{ pendingApproval.details }}</div>
                <div class="approval-actions">
                  <button class="btn-primary" :disabled="isApprovalSubmitting" @click="handleHumanApproval('approved')">
                    {{ isApprovalSubmitting ? '处理中...' : (pendingApproval.approveLabel || '确认') }}
                  </button>
                  <button class="btn-secondary" :disabled="isApprovalSubmitting" @click="handleHumanApproval('rejected')">
                    {{ pendingApproval.rejectLabel || '取消' }}
                  </button>
                </div>
              </div>

              <div class="input-box">
                <input
                  v-model="userInput"
                  type="text"
                  class="chat-input"
                  placeholder="请输入您的问题..."
                  :disabled="isProcessing || !!pendingApproval"
                  @keyup.enter.exact="handleSend($event)"
                />
                <button
                  class="send-btn"
                  :class="{ 'cancel-btn': isProcessing }"
                  :disabled="(!userInput.trim() && !isProcessing) || !!pendingApproval"
                  @click="isProcessing ? handleCancel() : handleSend()"
                >
                  <svg v-if="!isProcessing" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                  <span v-else class="stop-icon">■</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch (error) {
    console.error('Markdown parsing error:', error)
    return text
  }
}

const validUsers = [
  { username: 'root1', password: '123456', userId: 'root1' },
  { username: 'root2', password: '123456', userId: 'root2' },
  { username: 'root3', password: '123456', userId: 'root3' }
]

const reviewStatusLabels = {
  supported: '已核验',
  unsupported: '需谨慎',
  conflicting: '证据冲突',
  review_unavailable: '待复核'
}

const intentLabels = {
  technical_support: '技术支持',
  knowledge_base: '知识库问答',
  service_station: '维修站查询',
  navigation: '导航信息'
}

const evidenceSourceLabels = {
  knowledge_base: '知识库 RAG',
  retrieval: '检索结果',
  web_search: '网页搜索',
  web_search_preview: '网页搜索',
  bailian_web_search: '网页搜索',
  internet_search: '网页搜索',
  service_station: '维修站工具',
  geocode: '定位服务',
  navigation: '导航服务'
}

const normalizeReviewVerdict = (reviewVerdict) => {
  if (!reviewVerdict || typeof reviewVerdict !== 'object') return null
  return {
    status: reviewVerdict.status || 'supported',
    summary: reviewVerdict.summary || '',
    shouldDowngrade: Boolean(reviewVerdict.should_downgrade),
    reviewed: reviewVerdict.reviewed !== false
  }
}

const normalizeEvidenceCards = (evidenceCards) => {
  if (!Array.isArray(evidenceCards)) return []
  return evidenceCards
    .filter((card) => card && typeof card === 'object')
    .map((card) => ({
      title: card.title || '',
      snippet: card.snippet || '',
      source: card.source || '',
      uri: card.uri || ''
    }))
}

const extractAssistantMetadata = (payload = {}) => {
  const reviewVerdict = normalizeReviewVerdict(payload.review_verdict || payload.reviewVerdict)
  const evidenceCards = normalizeEvidenceCards(payload.evidence_cards || payload.evidenceCards)
  const references = Array.isArray(payload.references) ? [...payload.references] : []
  const rawIntent = payload.intent || ''
  return {
    reviewVerdict,
    evidenceCards,
    references,
    nextAction: payload.next_action || payload.nextAction || '',
    intent: rawIntent === 'general' ? '' : rawIntent
  }
}

const hasAssistantMetadata = (metadata = {}) => {
  return Boolean(
    metadata.reviewVerdict ||
    (Array.isArray(metadata.evidenceCards) && metadata.evidenceCards.length > 0) ||
    (Array.isArray(metadata.references) && metadata.references.length > 0) ||
    metadata.nextAction ||
    metadata.intent
  )
}

const classifyEvidenceSource = (source = '') => {
  const normalized = String(source || '').toLowerCase()
  if (normalized.includes('knowledge')) return 'rag'
  if (normalized.includes('web_search') || normalized.includes('internet') || normalized.includes('search')) return 'web'
  if (normalized.includes('service_station') || normalized.includes('navigation') || normalized.includes('geocode')) return 'service'
  return 'other'
}

const formatEvidenceSource = (source = '') => {
  const normalized = String(source || '').toLowerCase()
  return evidenceSourceLabels[normalized] || '参考依据'
}

export default {
  name: 'ChatPage',
  setup() {
    const isLoggedIn = ref(true)
    const isSidebarExpanded = ref(true)
    const username = ref('')
    const password = ref('')
    const currentUser = ref('')
    const loginError = ref('')
    const showUserInfo = ref(false)
    const avatarContainerRef = ref(null)

    const userInput = ref('')
    const chatMessages = ref([])
    const processMessages = ref([])
    const answerText = ref('')
    const isProcessing = ref(false)
    const pendingApproval = ref(null)
    const isApprovalSubmitting = ref(false)
    const sessions = ref([])
    const selectedSessionId = ref('')
    const isLoadingSessions = ref(false)
    const showSessions = ref(true)
    let reader = null

    const savedUserId = localStorage.getItem('currentUserId')
    if (savedUserId) {
      const savedUser = validUsers.find((user) => user.userId === savedUserId)
      if (savedUser) {
        currentUser.value = savedUser.username
      }
    }

    const toggleUserInfo = () => {
      showUserInfo.value = !showUserInfo.value
    }

    const handleClickOutside = (event) => {
      if (showUserInfo.value && avatarContainerRef.value && !avatarContainerRef.value.contains(event.target)) {
        showUserInfo.value = false
      }
    }

    const toggleThinking = (index) => {
      const msg = chatMessages.value[index]
      if (msg?.type === 'THINKING' || msg?.type === 'PROCESS_CARD') {
        msg.collapsed = !msg.collapsed
      }
    }

    const toggleSessions = () => {
      showSessions.value = !showSessions.value
    }

    const handleLogin = () => {
      loginError.value = ''
      const user = validUsers.find((item) => item.username === username.value && item.password === password.value)

      if (!user) {
        loginError.value = '用户名或密码错误'
        return
      }

      isLoggedIn.value = true
      currentUser.value = user.username
      localStorage.setItem('currentUserId', user.userId)
      username.value = ''
      password.value = ''
      window.scrollTo(0, 0)
    }

    const handleLogout = () => {
      isLoggedIn.value = false
      currentUser.value = ''
      localStorage.removeItem('currentUserId')
      chatMessages.value = []
      processMessages.value = []
      answerText.value = ''
      userInput.value = ''
      sessions.value = []
      selectedSessionId.value = ''
      pendingApproval.value = null
    }

    const goToLogin = () => {
      handleLogout()
    }

    const scrollToBottom = () => {
      setTimeout(() => {
        const chatContainer = document.querySelector('.chat-message-container')
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight
        }
        window.scrollTo(0, 0)
      }, 0)
    }

    const formatReviewStatus = (status) => reviewStatusLabels[status] || '审核信息'

    const formatIntentLabel = (intent) => intentLabels[intent] || ''

    const formatEvidenceSourceLabel = (source) => formatEvidenceSource(source)

    const hasAssistantDiagnostics = (message) => hasAssistantMetadata(message)

    const applyAssistantMetadata = (targetMessage, metadata = {}) => {
      if (!targetMessage || targetMessage.type !== 'assistant' || !hasAssistantMetadata(metadata)) {
        return
      }

      if (metadata.reviewVerdict) {
        targetMessage.reviewVerdict = metadata.reviewVerdict
      }
      if (metadata.evidenceCards?.length) {
        targetMessage.evidenceCards = metadata.evidenceCards
      }
      if (metadata.references?.length) {
        targetMessage.references = metadata.references
      }
      if (metadata.nextAction) {
        targetMessage.nextAction = metadata.nextAction
      }
      if (metadata.intent) {
        targetMessage.intent = metadata.intent
      }
      if (typeof targetMessage.evidenceExpanded !== 'boolean') {
        targetMessage.evidenceExpanded = false
      }
    }

    const createAssistantMessage = (content = '', metadata = {}) => {
      const message = {
        type: 'assistant',
        content,
        evidenceExpanded: false
      }
      applyAssistantMetadata(message, metadata)
      return message
    }

    const normalizeMemoryRole = (role) => {
      if (role === 'process') return 'THINKING'
      return role
    }

    const normalizeSessionMessage = (msg) => {
      const type = normalizeMemoryRole(msg.role)
      if (type === 'assistant') {
        return createAssistantMessage(msg.content || '', extractAssistantMetadata(msg))
      }
      return {
        type,
        content: msg.content || '',
        collapsed: false
      }
    }

    const selectSession = (sessionId) => {
      selectedSessionId.value = sessionId
      const session = sessions.value.find((item) => item.session_id === sessionId)
      chatMessages.value = []
      processMessages.value = []
      answerText.value = ''
      pendingApproval.value = session?.pending_approval || null

      if (!session?.memory?.length) return

      let lastType = null
      session.memory.forEach((msg) => {
        if (!msg?.content) return
        const normalizedMessage = normalizeSessionMessage(msg)
        const type = normalizedMessage.type

        if (type === 'THINKING' && lastType === 'THINKING') {
          chatMessages.value[chatMessages.value.length - 1].content += `\n${msg.content}`
        } else {
          chatMessages.value.push(normalizedMessage)
        }
        lastType = type
      })

      nextTick(scrollToBottom)
    }

    const fetchUserSessions = async () => {
      if (!currentUser.value) return

      isLoadingSessions.value = true
      try {
        const response = await fetch('http://127.0.0.1:8000/api/user_sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: currentUser.value })
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()
        if (data.success && Array.isArray(data.sessions)) {
          sessions.value = data.sessions
          if (selectedSessionId.value) {
            const currentSession = data.sessions.find((item) => item.session_id === selectedSessionId.value)
            pendingApproval.value = currentSession?.pending_approval || null
          }
          if (data.sessions.length > 0 && !selectedSessionId.value) {
            selectSession(data.sessions[0].session_id)
          }
        }
      } catch (error) {
        console.error('Error fetching sessions:', error)
      } finally {
        isLoadingSessions.value = false
        scrollToBottom()
      }
    }

    const createNewSession = () => {
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
      sessions.value.unshift({
        session_id: newSessionId,
        create_time: new Date().toISOString(),
        memory: [],
        total_messages: 0
      })
      chatMessages.value = []
      processMessages.value = []
      answerText.value = ''
      userInput.value = ''
      selectedSessionId.value = newSessionId
      pendingApproval.value = null
    }

    const streamTextToAnswer = (text = '', metadata = {}) => {
      const lastMsg = chatMessages.value[chatMessages.value.length - 1]
      const normalizedText = (text || '').replace(/ +/g, ' ').replace(/\n+/g, '\n')
      const hasText = Boolean(normalizedText.trim())
      const hasMetadata = hasAssistantMetadata(metadata)

      if (!hasText && !hasMetadata) {
        return
      }

      if (lastMsg && lastMsg.type === 'assistant') {
        if (hasText) {
          if (hasMetadata) {
            lastMsg.content = normalizedText
          } else {
            lastMsg.content += normalizedText
          }
        }
        applyAssistantMetadata(lastMsg, metadata)
      } else {
        chatMessages.value.push(createAssistantMessage(hasText ? normalizedText : '', metadata))
      }
      chatMessages.value = [...chatMessages.value]
      if (hasText) {
        answerText.value = hasMetadata ? normalizedText : (answerText.value + normalizedText)
      }
      scrollToBottom()
    }

    const getProcessCard = () => chatMessages.value.findLast((msg) => msg.type === 'PROCESS_CARD')

    const ensureProcessCard = () => {
      let processCard = getProcessCard()
      if (!processCard) {
        processCard = {
          type: 'PROCESS_CARD',
          steps: [],
          collapsed: false,
          status: 'running',
          summary: 'Agent 正在处理你的请求'
        }
        chatMessages.value.push(processCard)
      }
      return processCard
    }

    const stripHtml = (text) => (text || '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()

    const normalizeProcessStep = (text, kind = 'PROCESS') => {
      const cleanedText = stripHtml(text)
      if (!cleanedText) return null

      if (cleanedText.includes('[查询分析]')) {
        return {
          key: 'query_analysis',
          label: '查询分析',
          detail: cleanedText.replace('[查询分析]', '').trim()
        }
      }

      if (cleanedText.includes('智能体切换') || cleanedText.includes('当前接管')) {
        return {
          key: 'agent_switch',
          label: '智能体切换',
          detail: cleanedText.replace('智能体切换', '').trim()
        }
      }

      if (cleanedText.includes('正在调用工具') || cleanedText.includes('调度中心') || cleanedText.includes('工具')) {
        return {
          key: 'tool_call',
          label: '调用工具',
          detail: cleanedText.replace('正在调用工具', '').trim()
        }
      }

      if (kind === 'HUMAN_APPROVAL' || cleanedText.includes('审批') || cleanedText.includes('确认')) {
        return {
          key: 'waiting_approval',
          label: '等待审批',
          detail: cleanedText
        }
      }

      if (cleanedText.includes('取消')) {
        return {
          key: 'cancelled',
          label: '已取消',
          detail: cleanedText
        }
      }

      return null
    }

    const appendProcessStep = (step) => {
      if (!step) return

      const processCard = ensureProcessCard()
      const existingStep = processCard.steps[processCard.steps.length - 1]
      if (existingStep && existingStep.key === step.key && existingStep.detail === step.detail) {
        return
      }

      processCard.steps.push(step)
      processCard.summary = step.label + (step.detail ? ` · ${step.detail}` : '')
      if (step.key === 'waiting_approval') {
        processCard.status = 'waiting_approval'
        processCard.collapsed = false
      } else if (step.key === 'cancelled') {
        processCard.status = 'cancelled'
      } else if (processCard.status !== 'waiting_approval') {
        processCard.status = 'running'
      }
      chatMessages.value = [...chatMessages.value]
      scrollToBottom()
    }

    const finalizeProcessCard = (status = 'completed') => {
      const processCard = getProcessCard()
      if (!processCard) return
      processCard.status = status
      processCard.collapsed = status === 'completed'
      if (status === 'completed' && processCard.steps.length > 0) {
        const lastStep = processCard.steps[processCard.steps.length - 1]
        processCard.summary = lastStep.label + (lastStep.detail ? ` · ${lastStep.detail}` : '')
      }
      chatMessages.value = [...chatMessages.value]
    }

    const streamTextToProcess = (text) => {
      const lastMsg = chatMessages.value[chatMessages.value.length - 1]
      if (lastMsg && lastMsg.type === 'THINKING') {
        lastMsg.content += text
      } else {
        chatMessages.value.push({
          type: 'THINKING',
          content: text,
          collapsed: false
        })
      }
      chatMessages.value = [...chatMessages.value]

      const lastProcessMsg = processMessages.value[processMessages.value.length - 1]
      if (lastProcessMsg && lastProcessMsg.type === 'THINKING') {
        lastProcessMsg.text += text
        processMessages.value = [...processMessages.value]
      } else {
        processMessages.value = [...processMessages.value, { type: 'THINKING', text }]
      }

      scrollToBottom()
    }

    const stopThinkingAnimation = () => {}

    const processSSEData = (data) => {
      try {
        if (typeof data !== 'string' || !data.startsWith('data:')) return

        const jsonStr = data.slice(5).trim()
        if (!jsonStr) return

        const parsedData = JSON.parse(jsonStr)
        let kind
        let text

        let answerMetadata = {}

        if (parsedData.content && typeof parsedData.content === 'object') {
          text = parsedData.content.text
          answerMetadata = extractAssistantMetadata(parsedData.content)

          if (parsedData.content.contentType === 'sagegpt/human_approval') {
            pendingApproval.value = {
              token: parsedData.content.token,
              title: parsedData.content.title,
              question: parsedData.content.question,
              details: parsedData.content.details,
              approveLabel: parsedData.content.approveLabel,
              rejectLabel: parsedData.content.rejectLabel
            }
            kind = 'HUMAN_APPROVAL'
            text = parsedData.content.question || ''
          }

          kind = parsedData.content.kind || parsedData.content.type || kind

          if (parsedData.status === 'FINISHED' || parsedData.content.contentType === 'sagegpt/finish') {
            return
          }
        } else if (parsedData.type && parsedData.content) {
          kind = parsedData.type
          text = parsedData.content
        }

        if (!kind) return

        switch (kind) {
          case 'ANSWER':
            stopThinkingAnimation()
            finalizeProcessCard('completed')
            streamTextToAnswer(text || '', answerMetadata)
            break
          case 'THINKING':
            break
          case 'PROCESS':
            appendProcessStep(normalizeProcessStep(text, kind))
            break
          case 'HUMAN_APPROVAL':
            appendProcessStep(normalizeProcessStep(text, kind))
            isProcessing.value = false
            scrollToBottom()
            break
          default:
            appendProcessStep(normalizeProcessStep(text, kind))
        }
      } catch (error) {
        console.error('Error processing SSE data:', error)
      }
    }

    const startSSERequest = async (url, requestData) => {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('服务端未返回可读取的流式响应')
      }

      const activeReader = response.body.getReader()
      reader = activeReader
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await activeReader.read()
        if (done) {
          if (buffer.trim()) {
            processSSEData(buffer)
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        for (let i = 0; i < lines.length - 1; i += 1) {
          const line = lines[i]
          if (line.trim()) {
            processSSEData(line)
          }
        }
        buffer = lines[lines.length - 1]
      }
    }

    const handleHumanApproval = async (decision) => {
      if (!pendingApproval.value || isApprovalSubmitting.value) return

      const userId = localStorage.getItem('currentUserId') || currentUser.value
      const approvalToken = pendingApproval.value.token
      isApprovalSubmitting.value = true
      isProcessing.value = true
      pendingApproval.value = null

      try {
        await startSSERequest('http://127.0.0.1:8000/api/human_approval', {
          approval_token: approvalToken,
          decision,
          context: {
            user_id: userId,
            session_id: selectedSessionId.value || ''
          }
        })
      } catch (error) {
        if (error.name !== 'AbortError') {
          appendProcessStep({
            key: 'approval_error',
            label: '等待审批',
            detail: `审批处理失败: ${error.message}`
          })
        }
      } finally {
        isApprovalSubmitting.value = false
        isProcessing.value = false
        if (decision === 'rejected') {
          pendingApproval.value = null
          finalizeProcessCard('cancelled')
        }
        reader = null
        fetchUserSessions()
        scrollToBottom()
      }
    }

    const handleSend = async (event) => {
      if (event) {
        event.preventDefault()
      }
      if (!userInput.value.trim() || pendingApproval.value) return

      window.scrollTo(0, 0)
      const userId = localStorage.getItem('currentUserId')
      if (!userId) {
        isLoggedIn.value = false
        return
      }

      isProcessing.value = true
      chatMessages.value.forEach((msg) => {
        if (msg.type === 'THINKING' || msg.type === 'PROCESS_CARD') {
          msg.collapsed = true
        }
      })
      processMessages.value = []
      chatMessages.value.push({ type: 'user', content: userInput.value.trim() })
      ensureProcessCard()
      appendProcessStep({
        key: 'query_analysis',
        label: '查询分析',
        detail: `原始问题: ${userInput.value.trim()}`
      })
      answerText.value += `<div class="user-message">${userInput.value.trim()}</div>\n\n`
      scrollToBottom()

      const requestData = {
        query: userInput.value.trim(),
        context: {
          user_id: userId || currentUser.value,
          session_id: selectedSessionId.value || ''
        }
      }

      try {
        const response = await fetch('http://127.0.0.1:8000/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestData)
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        if (!response.body) {
          throw new Error('服务端未返回可读取的流式响应')
        }

        const activeReader = response.body.getReader()
        reader = activeReader
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await activeReader.read()
          if (done) {
            if (buffer.trim()) {
              processSSEData(buffer)
            }
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          for (let i = 0; i < lines.length - 1; i += 1) {
            const line = lines[i]
            if (line.trim()) {
              processSSEData(line)
            }
          }
          buffer = lines[lines.length - 1]
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          const errorMsg = `请求失败: ${error.message}`
          appendProcessStep({
            key: 'request_error',
            label: '处理异常',
            detail: errorMsg
          })
          console.error('Error:', error)
        }
      } finally {
        isProcessing.value = false
        reader = null
        scrollToBottom()
        fetchUserSessions()
      }

      userInput.value = ''
    }

    const handleCancel = () => {
      if (reader) {
        reader.cancel()
        reader = null
      }
      isProcessing.value = false
      stopThinkingAnimation()
      appendProcessStep({
        key: 'cancelled',
        label: '已取消',
        detail: '请求已取消'
      })
      finalizeProcessCard('cancelled')
    }

    const handleKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault()
        createNewSession()
      }
    }

    const toggleSidebar = () => {
      isSidebarExpanded.value = !isSidebarExpanded.value
    }

    watch(isLoggedIn, (newVal) => {
      if (newVal && currentUser.value) {
        fetchUserSessions()
      }
    })

    onMounted(() => {
      document.addEventListener('click', handleClickOutside)
      document.addEventListener('keydown', handleKeyDown)
      if (isLoggedIn.value && currentUser.value) {
        fetchUserSessions()
        nextTick(scrollToBottom)
      }
    })

    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    })

    return {
      isLoggedIn,
      isSidebarExpanded,
      username,
      password,
      currentUser,
      loginError,
      showUserInfo,
      avatarContainerRef,
      userInput,
      chatMessages,
      isProcessing,
      pendingApproval,
      isApprovalSubmitting,
      sessions,
      selectedSessionId,
      isLoadingSessions,
      showSessions,
      toggleUserInfo,
      toggleThinking,
      toggleSessions,
      handleLogin,
      handleLogout,
      goToLogin,
      createNewSession,
      selectSession,
      handleHumanApproval,
      handleSend,
      handleCancel,
      toggleSidebar,
      formatReviewStatus,
      formatIntentLabel,
      formatEvidenceSource: formatEvidenceSourceLabel,
      classifyEvidenceSource,
      hasAssistantDiagnostics,
      renderMarkdown
    }
  }
}
</script>

<style scoped>
.model-down {
  padding-left: 50px;
  margin-top: 10px;
}

.process-card-content {
  padding: 0;
}

.agent-process-card {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background: linear-gradient(180deg, #fafaf7 0%, #f4f6ef 100%);
  overflow: hidden;
}

.agent-process-header {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  text-align: left;
  cursor: pointer;
}

.agent-process-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 110px;
}

.agent-process-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #94a3b8;
  flex-shrink: 0;
}

.agent-process-status-dot.running {
  background: #f59e0b;
}

.agent-process-status-dot.completed {
  background: #16a34a;
}

.agent-process-status-dot.waiting_approval {
  background: #2563eb;
}

.agent-process-status-dot.cancelled {
  background: #64748b;
}

.agent-process-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.agent-process-header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.agent-process-summary {
  font-size: 13px;
  color: #475569;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-process-body {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-process-step {
  padding-left: 14px;
  border-left: 2px solid rgba(37, 99, 235, 0.2);
}

.agent-process-step-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.agent-process-step-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.assistant-diagnostics {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.assistant-review-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.assistant-review-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
  border: 1px solid transparent;
}

.assistant-review-pill.review-supported {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
  border-color: rgba(22, 163, 74, 0.18);
}

.assistant-review-pill.review-unsupported,
.assistant-review-pill.review-conflicting {
  background: rgba(217, 119, 6, 0.12);
  color: #9a3412;
  border-color: rgba(217, 119, 6, 0.18);
}

.assistant-review-pill.review-review_unavailable,
.assistant-review-pill.review-neutral {
  background: rgba(15, 23, 42, 0.06);
  color: #334155;
  border-color: rgba(15, 23, 42, 0.1);
}

.assistant-review-summary,
.assistant-next-action {
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.assistant-next-action {
  padding-left: 12px;
  border-left: 2px solid rgba(37, 99, 235, 0.2);
}

.evidence-card-list {
  display: grid;
  gap: 10px;
}

.evidence-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 14px;
  background: #f8fbff;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.evidence-toggle-meta {
  margin-left: auto;
  font-size: 12px;
  color: #475569;
}

.evidence-toggle-action {
  font-size: 12px;
  color: #2563eb;
}

.evidence-card-stack {
  display: grid;
  gap: 10px;
}

.evidence-card {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.95) 0%, rgba(241, 245, 249, 0.98) 100%);
}

.evidence-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.evidence-card-source {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #334155;
  background: rgba(148, 163, 184, 0.15);
}

.evidence-card-source.source-rag {
  background: rgba(14, 116, 144, 0.14);
  color: #155e75;
}

.evidence-card-source.source-web {
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.evidence-card-source.source-service {
  background: rgba(22, 163, 74, 0.14);
  color: #166534;
}

.evidence-card-link {
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
  text-decoration: none;
}

.evidence-card-link:hover {
  text-decoration: underline;
}

.evidence-card-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.evidence-card-snippet {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}

.sidebar-wrapper {
  position: relative;
  overflow: visible;
}

.sidebar-reopen-btn {
  position: absolute;
  top: 22px;
  right: -14px;
  z-index: 40;
  width: 28px;
  height: 56px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.96);
  color: #0f172a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  cursor: pointer;
  font-size: 18px;
  font-weight: 700;
}

.sidebar-reopen-btn:hover {
  background: #ffffff;
}
</style>
