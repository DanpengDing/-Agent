<template>
  <div class="app-container">
    <!-- 登录页面 -->
    <div v-if="!isLoggedIn" class="login-container">
      <div class="login-form">
        <div class="its-logo-flat login-logo">
            <img src="/its-logo.svg" alt="Multi-Agent Logo" width="60" height="60"/>
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
        <div v-if="loginError" class="login-error">
          {{ loginError }}
        </div>
        <button class="login-button btn-primary" @click="handleLogin">
          登录
        </button>
        <div class="login-hint">
          <p>测试用户：root1, root2, root3</p>
          <p>密码：123456</p>
        </div>
      </div>
    </div>
    
    <!-- 主界面（登录后显示） -->
    <template v-else>
      <!-- 移除header部分，将用户信息移到结果框右上角 -->
      
      <div class="main-content">
        <!-- 左侧历史会话列表 - 可展开收起 -->
        <div class="sidebar-wrapper">
          <!-- 侧边栏内容 -->
          <div class="sidebar-content" :class="{ 'expanded': isSidebarExpanded }">
            <!-- 简洁的顶部标题栏 -->
            <div class="header-bar">
              <div class="header-logo">
                <img src="/its-logo.svg" alt="Logo" width="32" height="32"/>
                <span class="header-title">智慧服务</span>
              </div>
              <button
                class="toggle-sidebar-btn"
                @click="toggleSidebar"
                :title="isSidebarExpanded ? '收起侧边栏' : '展开侧边栏'"
              >
                {{ isSidebarExpanded ? '‹' : '›' }}
              </button>
            </div>
            
            <!-- 新建会话按钮 - 放到logo下方并左右拉伸 -->
            <div class="session-button-container" v-show="isSidebarExpanded">
              <a href="/" class="new-chat-btn" @click.prevent="createNewSession">
                <span class="icon">
                  <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" role="img" style="" width="20" height="20" viewBox="0 0 1024 1024" name="AddConversation" class="iconify new-icon" data-v-9f34fd85="">
                    <path d="M475.136 561.152v89.74336c0 20.56192 16.50688 37.23264 36.864 37.23264s36.864-16.67072 36.864-37.23264v-89.7024h89.7024c20.60288 0 37.2736-16.54784 37.2736-36.864 0-20.39808-16.67072-36.864-37.2736-36.864H548.864V397.63968A37.0688 37.0688 0 0 0 512 360.448c-20.35712 0-36.864 16.67072-36.864 37.2736v89.7024H385.4336a37.0688 37.0688 0 0 0-37.2736 36.864c0 20.35712 16.67072 36.864 37.2736 36.864h89.7024z" fill="currentColor"></path>
                    <path d="M512 118.784c-223.96928 0-405.504 181.57568-405.504 405.504 0 78.76608 22.44608 152.3712 61.35808 214.6304l-44.27776 105.6768a61.44 61.44 0 0 0 56.68864 85.1968H512c223.92832 0 405.504-181.53472 405.504-405.504 0-223.92832-181.57568-405.504-405.504-405.504z m-331.776 405.504a331.776 331.776 0 1 1 331.73504 331.776H198.656l52.59264-125.5424-11.59168-16.62976A330.09664 330.09664 0 0 1 180.224 524.288z" fill="currentColor"></path>
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
            
            <!-- 历史会话列表 -->
            <div class="history-section">
              <div class="history-header" @click="toggleSessions">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 1024 1024" class="nav-icon">
                  <path d="M512 81.066667c-233.301333 0-422.4 189.098667-422.4 422.4s189.098667 422.4 422.4 422.4 422.4-189.098667 422.4-422.4-189.098667-422.4-422.4-422.4z m-345.6 422.4a345.6 345.6 0 1 1 691.2 0 345.6 345.6 0 1 1-691.2 0z m379.733333-174.933334a38.4 38.4 0 0 0-76.8 0v187.733334a38.4 38.4 0 0 0 11.264 27.136l93.866667 93.866666a38.4 38.4 0 1 0 54.272-54.272L546.133333 500.352V328.533333z" fill="currentColor"></path>
                </svg>
                <span class="nav-text">历史会话</span>
              </div>
              <div class="sessions-list" v-show="showSessions">
                <div v-if="isLoadingSessions" class="loading-sessions">
                  加载中...
                </div>
                <div v-else-if="sessions.length === 0" class="no-sessions">
                  暂无记录
                </div>
                <div
                  v-for="session in sessions"
                  :key="session.session_id"
                  :class="['session-item', { 'selected': session.session_id === selectedSessionId }]"
                  @click="selectSession(session.session_id)"
                >
                  <img alt="会话" src="//lf-flow-web-cdn.doubao.com/obj/flow-doubao/doubao/chat/static/image/default.light.2ea4b2b4.png" class="session-icon">
                  <div class="session-preview">{{ session.memory[0]?.content || '空对话' }}</div>
                </div>
              </div>
            </div>
          </div>
          

        </div>
        
        <!-- 右侧显示区域 -->
        <div class="main-container">
          <!-- 简洁的聊天界面 -->
          <div class="chat-container" :class="{ 'processing': isProcessing }">
            <!-- 顶部用户信息 -->
            <div class="top-user-section">
              <div class="user-avatar-container" ref="avatarContainerRef">
                <img
                  src="https://p3-flow-imagex-sign.byteimg.com/user-avatar/assets/e7b19241fb224cea967dfaea35448102_1080_1080.png~tplv-a9rns2rl98-icon-tiny.png?rcl=202511070904143F9B891FA2E40D7123F0&rk3s=8e244e95&rrcfp=76e58463&x-expires=1765155855&x-signature=nqQBx1W9ABfrm%2FRKkEYZUzsYjE0%3D"
                  class="user-avatar"
                  alt="用户头像"
                  @click="toggleUserInfo"
                  tabindex="0"
                />
                <div class="user-info-dropdown" v-show="showUserInfo">
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

            <!-- 欢迎消息 - 仅在没有消息时显示 -->
            <div class="welcome-area" v-if="chatMessages.length === 0">
              <div class="welcome-icon">
                <img src="/its-logo.svg" alt="Logo" width="64" height="64"/>
              </div>
              <h2 class="welcome-title">你好，我是联想智能售后客服</h2>
              <p class="welcome-subtitle">请问有什么可以帮您？</p>
            </div>

            <!-- 消息展示区域 -->
            <div class="chat-message-container" ref="processContent">
              <div v-for="(msg, index) in chatMessages" :key="index" :class="['message-wrapper', msg.type]">
                 <!-- 消息头/角色标识 -->
                 <div class="message-role-label" v-if="msg.type === 'THINKING'" @click="toggleThinking(index)">
                   <div class="thinking-header">
                     <span class="thinking-text">{{ isProcessing && index === chatMessages.length - 1 ? '思考中...' : '思考过程' }}</span>
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
                       :class="{ 'collapsed': msg.collapsed }"
                     >
                       <polyline points="6 9 12 15 18 9"></polyline>
                     </svg>
                   </div>
                 </div>

                 <!-- 消息内容 -->
                 <div class="message-content" v-show="msg.type !== 'THINKING' || !msg.collapsed">
                   <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                 </div>
              </div>
            </div>

            <!-- 底部输入框 -->
            <div class="input-area">
              <!-- 审批卡片 -->
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

              <!-- 输入框 -->
              <div class="input-box">
                <input
                  type="text"
                  v-model="userInput"
                  class="chat-input"
                  placeholder="请输入您的问题..."
                  @keyup.enter.exact="handleSend($event)"
                  :disabled="isProcessing || !!pendingApproval"
                />
                <button
                  class="send-btn"
                  :class="{ 'cancel-btn': isProcessing }"
                  :disabled="((!userInput.trim() && !isProcessing) || !!pendingApproval)"
                  @click="isProcessing ? handleCancel() : handleSend()"
                >
                  <svg v-if="!isProcessing" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue';
import { marked } from 'marked';

// Configure marked options
marked.setOptions({
  breaks: true, // Enable line breaks
  gfm: true,    // Enable GitHub Flavored Markdown
});

// 使用marked库进行markdown渲染
const renderMarkdown = (text) => {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch (e) {
    console.error('Markdown parsing error:', e);
    return text;
  }
};

export default {
  name: 'App',
  setup() {
    // 登录相关状态
    const isLoggedIn = ref(true);
    // 侧边栏展开/收起状态
    const isSidebarExpanded = ref(true);
    const username = ref('');
    const password = ref('');
    const currentUser = ref('');
    const loginError = ref('');
    // 用户信息显示状态（用于头像点击显示用户信息）
    const showUserInfo = ref(false);
    // 头像和下拉框的引用
    const avatarContainerRef = ref(null);
    
    // 切换用户信息显示/隐藏
    const toggleUserInfo = () => {
      showUserInfo.value = !showUserInfo.value;
    };

    // 点击外部收起下拉菜单
    const handleClickOutside = (event) => {
      // 关闭用户信息下拉框
      if (showUserInfo.value && avatarContainerRef.value && !avatarContainerRef.value.contains(event.target)) {
        showUserInfo.value = false;
      }
      

    };
    
    // 生命周期钩子：组件挂载后添加事件监听器
    onMounted(() => {
      document.addEventListener('click', handleClickOutside);
    });
    
    // 生命周期钩子：组件卸载前移除事件监听器
    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside);
    });
    
    // 初始化时检查localStorage中的用户信息，恢复currentUser
    const savedUserId = localStorage.getItem('currentUserId');
    if (savedUserId) {
      // 定义测试用户列表，与handleLogin中保持一致
      const validUsers = [
        { username: 'root1', password: '123456', userId: 'root1' },
        { username: 'root2', password: '123456', userId: 'root2' },
        { username: 'root3', password: '123456', userId: 'root3' }
      ];
      
      // 查找对应的用户并设置currentUser
      const savedUser = validUsers.find(u => u.userId === savedUserId);
      if (savedUser) {
        currentUser.value = savedUser.username;
      }
    }
    
    // 主界面相关状态
    const userInput = ref('');
    const chatMessages = ref([]); // Unified chat history: { type: 'user'|'assistant'|'THINKING'|'PROCESS', content: string }
    const processMessages = ref([]); // Deprecated, kept for safety
    const answerText = ref(''); // Deprecated, kept for safety
    const processContent = ref(null);
    const isProcessing = ref(false); // 标记是否正在处理请求
    let reader = null; // 保存读取器引用，用于取消请求
    
    // 当前选中的导航项
    const pendingApproval = ref(null);
    const isApprovalSubmitting = ref(false);
    const selectedNavItem = ref('');
    


    // 切换思考过程的折叠状态
    const toggleThinking = (index) => {
      const msg = chatMessages.value[index];
      if (msg && msg.type === 'THINKING') {
        msg.collapsed = !msg.collapsed;
      }
    };
    
    // 暴露给模板
    // return {
    //   toggleThinking,
    //   isLoggedIn,
    //   username,
    //   password,
    //   currentUser,
    

    
    // 处理知识库查询
    const handleKnowledgeBase = () => {
      console.log('打开知识库查询');
      // 清空右侧内容但保持页面结构不变
      processMessages.value = [];
      answerText.value = '';
      processContent.value = null;
      selectedNavItem.value = 'knowledge';
      // 清除历史会话选中状态
      selectedSessionId.value = '';
    };
    
    // 处理服务站查询
    const handleNetworkSearch = () => {
  selectedNavItem.value = 'network';
  selectedSessionId.value = '';
  // 联网搜索功能逻辑可以在这里实现
};

const handleServiceStation = () => {
      console.log('打开服务站查询');
      // 清空右侧内容但保持页面结构不变
      processMessages.value = [];
      answerText.value = '';
      processContent.value = null;
      selectedNavItem.value = 'service';
      // 清除历史会话选中状态
      selectedSessionId.value = '';
    };
    
    // 历史会话相关状态
    const sessions = ref([]);
    const selectedSessionId = ref('');
    const isLoadingSessions = ref(false);
    const showSessions = ref(true); // 控制历史会话的显示/隐藏
    
    // 切换历史会话的显示/隐藏
    const toggleSessions = () => {
      showSessions.value = !showSessions.value;
    };

    // 处理登录
    const handleLogin = () => {
      // 清空错误信息
      loginError.value = '';
      
      // 定义测试用户列表
      const validUsers = [
        { username: 'root1', password: '123456', userId: 'root1' },
        { username: 'root2', password: '123456', userId: 'root2' },
        { username: 'root3', password: '123456', userId: 'root3' }
      ];
      
      // 查找用户
      const user = validUsers.find(u => u.username === username.value && u.password === password.value);
      
      if (user) {
        // 登录成功
        isLoggedIn.value = true;
        currentUser.value = user.username;
        // 保存用户ID（在实际应用中可能会保存token）
        localStorage.setItem('currentUserId', user.userId);
        // 登录成功后执行页面滚动到顶部
        window.scrollTo(0, 0);
        // 清空输入
        username.value = '';
        password.value = '';
      } else {
        // 登录失败
        loginError.value = '用户名或密码错误';
      }
    };

    // 获取历史会话数据
    const fetchUserSessions = async () => {
      if (!currentUser.value) return;
      
      isLoadingSessions.value = true;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/user_sessions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({"user_id": currentUser.value})
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success && data.sessions) {
          sessions.value = data.sessions;
          // 默认选择最新的会话
          if (data.sessions.length > 0 && !selectedSessionId.value) {
            selectSession(data.sessions[0].session_id);
          }
        }
      } catch (error) {
        console.error('Error fetching sessions:', error);
      } finally {
        isLoadingSessions.value = false;
        // 刷新会话列表后：确保最终结果框滚动到底部
        scrollToBottom();
      }
    };


    
    // 新建会话
    const createNewSession = () => {
      // 生成新的会话ID (使用时间戳+随机数确保唯一性)
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // 创建新会话对象
      const newSession = {
        session_id: newSessionId,
        create_time: new Date().toISOString(),
        memory: [],
        total_messages: 0
      };
      
      // 将新会话添加到会话列表的最前面
      sessions.value.unshift(newSession);
      
      // 清空当前内容
      processMessages.value = [];
      answerText.value = '';
      userInput.value = '';
      
      // 选中新会话
      selectSession(newSessionId);
    };
    
    // 选择会话
    const selectSession = (sessionId) => {
      selectedSessionId.value = sessionId;
      // 清除导航项选中状态
      selectedNavItem.value = '';
      // 找到选中的会话
      const session = sessions.value.find(s => s.session_id === sessionId);
      
      // 清空当前内容
      chatMessages.value = [];
      processMessages.value = [];
      answerText.value = '';
      
      if (session && session.memory && Array.isArray(session.memory) && session.memory.length > 0) {
        let lastType = null;
        
        session.memory.forEach(msg => {
          if (!msg || !msg.content) return;
          
          // 映射角色类型
          let type = msg.role;
          if (type === 'process') type = 'THINKING';
          
          // 合并连续的思考过程
          if (type === 'THINKING' && lastType === 'THINKING') {
            const lastMsg = chatMessages.value[chatMessages.value.length - 1];
            lastMsg.content += '\n' + msg.content;
          } else {
            chatMessages.value.push({
              type: type, // 'user', 'assistant', 'THINKING'
              content: msg.content
            });
          }
          lastType = type;
        });
        
        // 滚动到底部
        nextTick(() => {
          scrollToBottom();
        });
      }
    };
    
    // 处理登出
    const handleLogout = () => {
      isLoggedIn.value = false;
      currentUser.value = '';
      localStorage.removeItem('currentUserId');
      // 清空聊天内容
      processMessages.value = [];
      answerText.value = '';
      userInput.value = '';
      // 清空会话列表
      sessions.value = [];
      selectedSessionId.value = '';
    };
    
    // 跳转到登录页面
    const goToLogin = () => {
      isLoggedIn.value = false;
      currentUser.value = '';
      localStorage.removeItem('currentUserId');
    };
    
    // 处理发送请求
      const startSSERequest = async (url, requestData) => {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestData)
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            if (buffer.trim()) {
              processSSEData(buffer);
              buffer = '';
            }
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');

          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i];
            if (line.trim()) {
              processSSEData(line);
            }
          }

          buffer = lines[lines.length - 1];
        }
      };

      // 用户点确认/取消后，前端通过 approval_token 调 /api/human_approval。
      // 这样后端能够继续执行“刚才暂停的那一轮”，而不是新开一轮对话。
      const handleHumanApproval = async (decision) => {
        if (!pendingApproval.value || isApprovalSubmitting.value) return;

        const userId = localStorage.getItem('currentUserId') || currentUser.value;
        const approvalToken = pendingApproval.value.token;
        isApprovalSubmitting.value = true;
        isProcessing.value = true;
        pendingApproval.value = null;

        try {
          await startSSERequest('http://127.0.0.1:8000/api/human_approval', {
            approval_token: approvalToken,
            decision,
            context: {
              user_id: userId,
              session_id: selectedSessionId.value || ''
            }
          });
        } catch (error) {
          if (!error.name || error.name !== 'AbortError') {
            const errorMsg = `审批处理失败: ${error.message}`;
            streamTextToProcess(errorMsg + '\n');
          }
        } finally {
          isApprovalSubmitting.value = false;
          isProcessing.value = false;
          if (decision === 'rejected') {
            pendingApproval.value = null;
          }
          reader = null;
          fetchUserSessions();
          scrollToBottom();
        }
      };

      const handleSend = async (event) => {
        // 阻止回车键的默认行为（插入换行）
        if (event) {
          event.preventDefault();
        }
        if (!userInput.value.trim() || pendingApproval.value) return;
        
        // 立即强制滚动到页面顶部，防止页面下移
        window.scrollTo(0, 0);
        
        // 检查登录状态，只有点击发送时才检查
        const userId = localStorage.getItem('currentUserId');
        if (!userId) {
          // 如果没有登录凭证，跳转到登录页面
          isLoggedIn.value = false;
          return;
        }
        
        // 设置处理状态
        isProcessing.value = true;
        
        // 自动收起之前的思考过程
        chatMessages.value.forEach(msg => {
          if (msg.type === 'THINKING') {
            msg.collapsed = true;
          }
        });
        
        // 清空中间流程消息，但保留最终结果框中的历史会话内容
        // 注意：请求结束后会保留处理过程中的最后一条消息
        processMessages.value = [];
        
        // 将会话显示逻辑与历史会话保持一致：添加用户消息
        chatMessages.value.push({
          type: 'user',
          content: userInput.value.trim()
        });
        
        // 兼容旧变量（防止其他引用报错）
        const userMessage = `<div class="user-message">${userInput.value.trim()}</div>\n\n`;
        if (selectedSessionId.value && answerText.value) {
          answerText.value += userMessage;
        } else {
          answerText.value = userMessage;
        }
        
        // 确保userId有值，使用currentUser作为备选
        const finalUserId = userId || currentUser.value;
        
        // 请求发起时：添加用户消息后立即滚动到结果框底部
        scrollToBottom();
        
        // 准备请求数据，包含用户ID和选中的会话ID
        const requestData = {
          query: userInput.value.trim(),
          context: { 
            user_id: finalUserId,
            session_id: selectedSessionId.value || ''
          }
        };
        

        
        console.log('发送请求，会话ID:', selectedSessionId.value);
        
        console.log('发送请求，用户ID:', finalUserId);
        
        try {
          // 调用后端API
          const response = await fetch('http://127.0.0.1:8000/api/query', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
          });
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          
          // 处理流式响应
        reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
              // 处理最后一块数据
              if (buffer.trim()) {
                processSSEData(buffer);
                buffer = ''; // 清空缓冲区
              }
              break;
            }
          
          // 解码数据并累积到缓冲区
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          // 按行分割并处理完整的行
          const lines = buffer.split('\n');
          
          // 除了最后一行（可能不完整）外，处理所有行
          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i];
            if (line.trim()) {
              processSSEData(line);
            }
          }
          
          // 保留最后一行作为不完整的缓冲区
          buffer = lines[lines.length - 1];
        }
          
        } catch (error) {
          if (!error.name || error.name !== 'AbortError') {
            const errorMsg = `请求失败: ${error.message}`;
            streamTextToProcess(errorMsg + '\n');
            processMessages.value.push({
              type: 'PROCESS',
              text: errorMsg
            });
            console.error('Error:', error);
          }
        } finally {
          isProcessing.value = false;
          reader = null;
          
          // 请求结束时：确保最终结果框滚动到底部
          scrollToBottom();

          // 请求结束后，不自动收起思考过程，保持展开状态以便用户查看
          // const lastMsg = chatMessages.value[chatMessages.value.length - 1];
          // for (let i = chatMessages.value.length - 1; i >= 0; i--) {
          //    if (chatMessages.value[i].type === 'THINKING') {
          //      chatMessages.value[i].collapsed = true;
          //      break; 
          //    }
          // }
          
          // 会话请求结束后刷新历史会话区域
          fetchUserSessions();
        }
        
        // 清空输入框
        userInput.value = '';
      };
      
      // 处理SSE格式的数据
    // 统一解析后端 SSE。
    // 普通事件继续按 THINKING / PROCESS / ANSWER 渲染；
    // 但 human_approval 事件会转成审批卡片状态，不当作普通文本流处理。
    const processSSEData = (data) => {
      try {
        if (typeof data !== 'string') return;

        if (data.startsWith('data:')) {
          const jsonStr = data.substring(5).trim();

          if (jsonStr) {
            try {
              const parsedData = JSON.parse(jsonStr);

              let kind; // 变量名改为 kind
              let text;

              // -----------------------------------------------------------
              // 适配新的 StreamPacket 结构
              // 结构: { content: { kind: "...", text: "...", ... }, ... }
              // -----------------------------------------------------------
              if (parsedData.content && typeof parsedData.content === 'object') {
                // 1. 获取文本内容
                text = parsedData.content.text;

                if (parsedData.content.contentType === 'sagegpt/human_approval') {
                  // 后端发来这类事件，表示“当前任务已暂停，等待人工确认”。
                  // 前端只保存 token 和展示文案，真正继续执行要等用户点击按钮。
                  pendingApproval.value = {
                    token: parsedData.content.token,
                    title: parsedData.content.title,
                    question: parsedData.content.question,
                    details: parsedData.content.details,
                    approveLabel: parsedData.content.approveLabel,
                    rejectLabel: parsedData.content.rejectLabel
                  };
                  kind = 'HUMAN_APPROVAL';
                  text = parsedData.content.question || '';
                }

                // 2. 获取内容分类 (kind)
                if (parsedData.content.kind) {
                  // 新版后端字段名为 kind
                  kind = parsedData.content.kind;
                } else if (parsedData.content.type) {
                  // 兼容旧版字段名 type
                  kind = parsedData.content.type;
                }

                // 3. 处理结束信号 (如果内容是 FinishMessageBody)
                if (parsedData.status === 'FINISHED' || parsedData.content.contentType === 'sagegpt/finish') {
                   // 可以在这里处理结束逻辑，目前前端主要靠流结束自动处理
                   return;
                }
              }

              // -----------------------------------------------------------
              // 降级兼容旧逻辑 (防止后端回滚导致前端挂掉)
              // -----------------------------------------------------------
              else if (parsedData.type && parsedData.content) {
                kind = parsedData.type;
                text = parsedData.content;
              }

              // -----------------------------------------------------------
              // 根据 kind 分发处理逻辑
              // -----------------------------------------------------------
              if (kind && text) {
                // console.log('Processing kind:', kind, 'text:', text); // 调试日志

                switch (kind) {
                  case 'ANSWER':
                    stopThinkingAnimation();
                    streamTextToAnswer(text);
                    break;

                  case 'THINKING':
                    streamTextToProcess(text);
                    break;

                  case 'PROCESS':
                    streamTextToProcess(text + '\n');
                    // 兼容旧的 processMessages 数组
                    processMessages.value = [...processMessages.value, {
                      type: 'PROCESS', // 前端内部状态可以暂时保留叫 type，或者你也想改成 kind？建议暂时不动内部状态
                      text: text
                    }];
                    scrollToBottom();
                    break;

                  case 'HUMAN_APPROVAL':
                    // 进入待审批状态后，当前流式执行到此为止。
                    // 后续是否继续，取决于用户对审批卡片的操作。
                    isProcessing.value = false;
                    reader = null;
                    scrollToBottom();
                    break;

                  default:
                    console.log('Unknown content kind:', kind);
                    // 默认作为 PROCESS 处理
                    streamTextToProcess(text + '\n');
                }
              }
            } catch (jsonError) {
              console.error('JSON parse error:', jsonError);
            }
          }
        }
      } catch (error) {
        console.error('Error processing SSE data:', error);
      }
    };
      
      // 处理取消请求
      const handleCancel = () => {
        if (reader) {
          reader.cancel();
          reader = null;
        }
        isProcessing.value = false;
        // 取消请求时停止思考动画
        stopThinkingAnimation();
        
        streamTextToProcess('请求已取消\n');
        processMessages.value.push({
          type: 'PROCESS',
          text: '请求已取消'
        });
      };

    // 移除未使用的handleStreamingResponse函数

    // 流式更新答案文本（使用Markdown渲染）
    const streamTextToAnswer = (text) => {
      // 忽略打断思考过程的纯空白字符
      const lastMsg = chatMessages.value[chatMessages.value.length - 1];
      if ((!text || !text.trim()) && lastMsg && lastMsg.type !== 'assistant') {
        return;
      }

      // 处理文本：将多个空格替换为单个空格，多个换行替换为单个换行
      text = text
      // .replace(/[ \t]+/g, ' ')  // 将多个连续空白字符（包括空格、制表符等）替换为单个空格
      .replace(/ +/g, ' ')  // 将多个连续空白字符（包括空格、制表符等）替换为单个空格
      .replace(/\n+/g, '\n'); // 将多个连续换行符替换为单个换行符
      
      // 更新统一的聊天记录
      // const lastMsg = chatMessages.value[chatMessages.value.length - 1]; // 已在函数开头声明
      if (lastMsg && lastMsg.type === 'assistant') {
        lastMsg.content += text;
      } else {
        chatMessages.value.push({ type: 'assistant', content: text });
      }
      chatMessages.value = [...chatMessages.value]; // Trigger reactivity
      
      // 兼容旧变量
      answerText.value += text;
      
      // 后端返回数据时：确保最终结果框滚动到底部
      scrollToBottom();
    };
    
    // 流式更新处理消息
    const streamTextToProcess = (text) => {
      // 更新统一的聊天记录
      const lastMsg = chatMessages.value[chatMessages.value.length - 1];
      if (lastMsg && lastMsg.type === 'THINKING') {
        lastMsg.content += text;
        // 如果是新消息且正在处理中，确保展开
        if (isProcessing.value && lastMsg.collapsed === undefined) {
           // 使用 reactive 属性，初始化为 false (展开)
           lastMsg.collapsed = false;
        }
      } else {
        chatMessages.value.push({ 
          type: 'THINKING', 
          content: text,
          collapsed: false // 默认为展开状态
        });
      }
      chatMessages.value = [...chatMessages.value];
      
      // 兼容旧变量
      const lastProcessMsg = processMessages.value[processMessages.value.length - 1];
      if (lastProcessMsg && lastProcessMsg.type === 'THINKING') {
        lastProcessMsg.text += text;
        processMessages.value = [...processMessages.value];
      } else {
        processMessages.value = [...processMessages.value, {
          type: 'THINKING',
          text: text
        }];
      }
      
      scrollToBottom();
    };
    
    // 移除旧的思考动画逻辑，避免覆盖文本内容
    const startThinkingAnimation = () => {
      // 这里的逻辑已移除，由CSS处理动画效果
    };
    
    // 停止思考动画
    const stopThinkingAnimation = () => {
      // 这里的逻辑已移除
    };
    
    // 保留上面的processSSEData函数实现
      
      // 处理响应数据（兼容旧格式）
      const handleResponseData = (data) => {
        if (data.type === 'ANSWER') {
          // 收到答案时停止思考动画
          stopThinkingAnimation();
          streamTextToAnswer(data.content);
        } else if (data.type === 'THINKING') {
          // THINKING内容使用streamTextToProcess函数处理
          streamTextToProcess(data.content);
        } else if (data.type === 'PROCESS') {
          // 收到其他处理消息时停止思考动画
          stopThinkingAnimation();
          processMessages.value.push({ type: 'PROCESS', text: data.content });
          scrollToBottom();
        }
      };

    // 滚动到底部
    const scrollToBottom = () => {
      setTimeout(() => {
        // 滚动新的消息容器
        const chatContainer = document.querySelector('.chat-message-container');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        // 确保页面不整体滚动，无条件强制滚动到顶部
        window.scrollTo(0, 0);
      }, 0);
    };

    // 监听登录状态变化，登录成功后获取会话列表
    watch(isLoggedIn, (newVal) => {
      if (newVal && currentUser.value) {
        fetchUserSessions();
      }
    });
    
    // 组件挂载时检查登录状态并获取会话列表
    onMounted(() => {
      if (isLoggedIn.value && currentUser.value) {
        fetchUserSessions();

        // 组件挂载默认加载时：确保最终结果框滚动到底部
        nextTick(() => {
          scrollToBottom();
        });
      }
      
      // 添加键盘快捷键监听器
      document.addEventListener('keydown', handleKeyDown);
    });
    
    onUnmounted(() => {
      // 移除键盘快捷键监听器
      document.removeEventListener('keydown', handleKeyDown);
    });
    
    // 处理键盘快捷键
    const handleKeyDown = (event) => {
      // Ctrl+K 快捷键新建会话
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        createNewSession();
      }
    };
    
    // 切换侧边栏展开/收起状态
    const toggleSidebar = () => {
      isSidebarExpanded.value = !isSidebarExpanded.value;
      console.log('侧边栏状态:', isSidebarExpanded.value ? '展开' : '收起');
    };
    
    return {
      // 登录相关状态
      isLoggedIn,
      username,
      password,
      currentUser,
      loginError,
      showUserInfo,
      toggleUserInfo,
      avatarContainerRef,
      handleLogin,
      handleLogout,
      goToLogin,
      // 主界面相关
      userInput,
      chatMessages,
      processMessages,
      answerText,
      processContent,
      isProcessing,
      pendingApproval,
      isApprovalSubmitting,
      handleSend,
      handleHumanApproval,
      handleCancel,
      renderMarkdown,
      // 历史会话相关
      sessions,
      selectedSessionId,
      isLoadingSessions,
      showSessions,
      toggleSessions,
      // 导航栏相关
      selectedNavItem,
      handleKnowledgeBase,
  handleNetworkSearch,
  handleServiceStation,
      selectSession,
      fetchUserSessions,
      createNewSession,

      // 侧边栏相关
      isSidebarExpanded,
      toggleSidebar,
      // 思考过程相关
      toggleThinking
    };
  }
};
</script>

<style scoped>
/* 主要样式已在 style.css 中定义，这里仅保留必要的覆盖样式 */
.model-down {
  padding-left: 50px;
  margin-top: 10px;
}
</style>
