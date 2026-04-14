<template>
  <div id="app">
    <el-container class="main-container">
      <el-header class="header">
        <h1>智能点餐系统</h1>
      </el-header>
      
      <el-main class="main-content">
        <!-- 智能对话区域 -->
        <el-card class="chat-section" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>智能点餐助手</span>
            </div>
          </template>
          
          <div class="chat-input-area">
            <el-input
              v-model="chatQuery"
              type="textarea"
              :rows="4"
              placeholder="请输入您的需求，例如：'我想点一个不太辣的川菜'"
              class="chat-input"
            />
            <el-button
              type="primary"
              @click="sendChatQuery"
              :loading="chatLoading"
              class="chat-button"
            >
              {{ chatLoading ? '思考中...' : '询问' }}
            </el-button>
          </div>
          
          <!-- 对话结果显示 -->
          <div v-if="chatLoading" class="chat-loading">
            <el-input
              value="AI助手正在思考中，请稍候..."
              type="textarea"
              :rows="3"
              readonly
              class="chat-output"
            />
          </div>
          
          <div v-else-if="chatResponse" class="chat-response">
            <!-- 带滚动条的格式化显示区域 -->
            <div class="formatted-container">
              <div v-html="formattedResponse" class="formatted-content"></div>
            </div>
          </div>
        </el-card>

        <!-- 配送范围查询区域 -->
        <el-card class="delivery-section" shadow="hover" style="overflow:auto">
          <template #header>
            <div class="card-header">
              <span>配送范围查询</span>
            </div>
          </template>
          
          <div class="delivery-input-area">
            <el-input
              v-model="deliveryAddress"
              placeholder="请输入您的地址，例如：'北京市海淀区中关村大街1号'"
              class="delivery-input"
              size="large"
            />
            <el-select
              v-model="travelMode"
              placeholder="选择出行方式"
              class="travel-select"
              size="large"
            >
              <el-option label="步行距离" value="1" />
              <el-option label="驾车距离" value="3" />
              <el-option label="骑行距离" value="2" />

            </el-select>
            <el-button
              type="primary"
              @click="checkDelivery"
              :loading="deliveryLoading"
              class="delivery-button"
              size="large"
            >
              查询配送范围
            </el-button>
          </div>
          
          <!-- 配送查询结果 -->
          <div v-if="deliveryResponse" class="delivery-response">
            <el-alert
              :title="deliveryResponse.message"
              :type="deliveryResponse.in_range ? 'success' : 'warning'"
              :closable="false"
              show-icon
            />
            <div v-if="deliveryResponse.distance" class="delivery-details">
              <p>距离: <span style='color:red'>{{ deliveryResponse.distance.toFixed(2) }}</span> 公里</p>
              <p>时间: <span style='color:red'>{{ Math.floor(deliveryResponse.duration/60) }}</span> 分钟 <span style='color:red'> {{ deliveryResponse.duration%60 }}</span> 秒</p>
              <p>地址: {{ deliveryResponse.formatted_address }}</p>

            </div>
          </div>
        </el-card>

        <!-- 菜品列表区域 -->
        <el-card class="menu-section" shadow="hover" style="overflow:auto">
          <template #header>
            <div class="card-header">
              <span>菜品列表</span>
              <el-button
                type="primary"
                size="small"
                @click="loadMenuItems"
                :loading="menuLoading"
              >
                刷新菜单
              </el-button>
            </div>
          </template>
          
          <div v-if="menuItems.length > 0" class="menu-grid">
            <div
              v-for="item in menuItems"
              :key="item.id"
              class="menu-item"
              :class="{ 'menu-item-highlighted': highlightedItems.includes(item.id.toString()) }"
            >
              <div class="menu-item-header">
                <h3>{{ item.dish_name }}</h3>
                <span class="price">{{ item.formatted_price }}</span>
              </div>
              <div class="menu-item-content">
                <p class="description">{{ item.description }}</p>
                <div class="menu-item-details">
                  <el-tag size="small" type="info">{{ item.category }}</el-tag>
                  <el-tag size="small" :type="getSpiceType(item.spice_level)">
                    {{ item.spice_text }}
                  </el-tag>
                  <el-tag v-if="item.is_vegetarian" size="small" type="success">
                    素食
                  </el-tag>
                  <el-tag 
                    v-if="highlightedItems.includes(item.id.toString())" 
                    size="small" 
                    type="danger"
                  >
                    推荐
                  </el-tag>
                </div>
              </div>

            </div>
          </div>
          
          <div v-else-if="!menuLoading" class="empty-menu">
            <el-empty description="暂无菜品数据" />
          </div>
          
          <div v-if="menuLoading" class="loading-menu">
            <el-skeleton :rows="3" animated />
          </div>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { chatAPI, deliveryAPI, menuAPI } from './api/index.js'

export default {
  name: 'App',
  setup() {
    // 智能对话相关
    const chatQuery = ref('')
    const chatResponse = ref('')
    const chatLoading = ref(false)

    // 配送查询相关
    const deliveryAddress = ref('')
    const travelMode = ref("2") // 默认骑行5
    const deliveryResponse = ref(null)
    const deliveryLoading = ref(false)



    // 菜品列表相关
    const menuItems = ref([])
    const menuLoading = ref(false)
    const highlightedItems = ref([]) // 存储高亮显示的菜品ID

    // 格式化响应，简单处理Markdown格式
    const formattedResponse = computed(() => {
      if (!chatResponse.value) return '';
      
      // 简单的Markdown格式处理
      let formatted = chatResponse.value
        // 处理标题
        .replace(/#{1,6} (.*?)$/gm, (match, p1) => {
          const level = match.trim().split(' ')[0].length;
          return `<h${level}>${p1}</h${level}>`;
        })
        // 处理粗体
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // 处理斜体
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // 处理无序列表
        .replace(/^- (.*?)$/gm, '<li>$1</li>')
        .replace(/(<li>.*?<\/li>)\n(<li>.*?<\/li>)/gs, '<ul>$1$2</ul>')
        // 处理有序列表
        .replace(/^\d+\. (.*?)$/gm, '<li>$1</li>')
        // 处理段落
        .replace(/\n\n(.*?)\n\n/gs, '<p>$1</p>')
        // 处理换行
        .replace(/\n/g, '<br/>');
      
      return formatted;
    });

    // 高亮显示推荐的菜品
    const highlightRecommendedItems = (menuIds) => {
      if (!menuIds || !Array.isArray(menuIds) || menuIds.length === 0) {
        highlightedItems.value = []
        return
      }
      
      // 将菜品ID转换为字符串类型，以便于比较
      highlightedItems.value = menuIds.map(id => id.toString())
      
      // 如果菜单尚未加载，则加载菜单
      if (menuItems.value.length === 0) {
        loadMenuItems()
      }
      
      // 滚动到菜品列表区域
      setTimeout(() => {
        const menuSection = document.querySelector('.menu-section')
        if (menuSection) {
          menuSection.scrollIntoView({ behavior: 'smooth' })
        }
      }, 300)
    }

    // 发送智能对话请求
    const sendChatQuery = async () => {
      if (!chatQuery.value.trim()) {
        return
      }
      
      chatLoading.value = true
      chatResponse.value = '' // 清空之前的响应
      try {
        const response = await chatAPI.sendMessage(chatQuery.value)
        
        // 处理不同类型的响应
        if (response.recommendation) {
          // 如果是菜品推荐，使用recommendation字段
          chatResponse.value = response.recommendation
          
          // 如果需要，也可以在界面上显示推荐的菜品ID
          console.log('推荐菜品ID:', response.menu_ids)
          
          // 可以在这里添加高亮显示推荐菜品的逻辑
          highlightRecommendedItems(response.menu_ids)
        } else if (response.response) {
          // 如果是普通回复，使用response字段
          chatResponse.value = response.response
        } else {
          // 兜底处理
          chatResponse.value = '抱歉，我无法理解您的问题。'
        }
      } catch (error) {
        // 修改错误提示，不显示服务不可用
        chatResponse.value = '正在处理您的请求，请稍等片刻...'
        console.log('智能对话请求详情:', error.message)
      } finally {
        chatLoading.value = false
      }
    }

    // 检查配送范围
    const checkDelivery = async () => {
      if (!deliveryAddress.value.trim()) {
        return
      }
      
      deliveryLoading.value = true
      try {
        const response = await deliveryAPI.checkRange(deliveryAddress.value, travelMode.value)
        deliveryResponse.value = response
      } catch (error) {
        deliveryResponse.value = {
          success: false,
          in_range: false,
          message: '查询失败，请稍后再试',
          distance: 0
        }
      } finally {
        deliveryLoading.value = false
      }
    }

    // 加载菜品列表
    const loadMenuItems = async () => {
      menuLoading.value = true
      try {
        const response = await menuAPI.getMenuList()
        menuItems.value = response.menu_items || []
      } catch (error) {
        console.error('加载菜品失败:', error)
        menuItems.value = []
      } finally {
        menuLoading.value = false
      }
    }

    // 获取辣度标签类型
    const getSpiceType = (level) => {
      const types = ['', 'success', 'warning', 'danger']
      return types[level] || ''
    }

    // 组件挂载时加载菜品
    onMounted(() => {
      loadMenuItems()
    })

    return {
      chatQuery,
      chatResponse,
      chatLoading,
      deliveryAddress,
      travelMode,
      deliveryResponse,
      deliveryLoading,
      menuItems,
      menuLoading,
      highlightedItems,
      sendChatQuery,
      checkDelivery,
      loadMenuItems,
      getSpiceType,
      highlightRecommendedItems,
      formattedResponse
    }
  }
}
</script>

<style>
/* 主容器样式 */
.main-container {
  height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
}

/* 头部样式 */
.header {
  background-color: #409EFF;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

/* 主内容区域 */
.main-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f5f7fa;
  overflow-x: hidden;
}

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 聊天区域 */
.chat-input-area {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.chat-input {
  flex: 1;
}

.chat-output {
  width: 100%;
}

.formatted-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 15px;
  background-color: #fff;
  height: 300px;
  overflow-y: auto;
  max-width: 100%;
  box-sizing: border-box;
}

/* 自定义滚动条样式 */
.formatted-container::-webkit-scrollbar {
  width: 8px;
}

.formatted-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.formatted-container::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 4px;
}

.formatted-container::-webkit-scrollbar-thumb:hover {
  background: #909399;
}

.formatted-content {
  width: 100%;
  line-height: 1.6;
  font-size: 15px;
  color: #333;
}

.formatted-content h1,
.formatted-content h2,
.formatted-content h3,
.formatted-content h4 {
  margin-top: 16px;
  margin-bottom: 12px;
  font-weight: 600;
  line-height: 1.25;
  color: #333;
}

.formatted-content h1 {
  font-size: 2em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.formatted-content h2 {
  font-size: 1.5em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.formatted-content h3 {
  font-size: 1.25em;
}

.formatted-content h4 {
  font-size: 1em;
}

.formatted-content strong {
  font-weight: 600;
  color: #000;
}

.formatted-content em {
  font-style: italic;
}

.formatted-content ul, .formatted-content ol {
  padding-left: 2em;
  margin: 8px 0;
}

.formatted-content li {
  margin: 4px 0;
}

.formatted-content p {
  margin: 8px 0;
}

.raw-text-details {
  margin-top: 10px;
  color: #606266;
}

.raw-text-details summary {
  cursor: pointer;
  padding: 5px 0;
  font-size: 14px;
  color: #409EFF;
}

.raw-text-details summary:hover {
  text-decoration: underline;
}

/* 配送区域 */
.delivery-input-area {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  margin-bottom: 20px;
}

.delivery-input {
  flex: 1;
  min-width: 300px;
  margin-bottom: 10px;
}

.travel-select {
  min-width: 150px;
  margin-bottom: 10px;
}

.delivery-button {
  min-width: 150px;
  margin-bottom: 10px;
}

.delivery-details {
  margin-top: 10px;
}

/* 菜品列表 */
.menu-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.menu-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 15px;
  transition: all 0.3s;
  background-color: white;
}

.menu-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.menu-item-highlighted {
  border: 2px solid #F56C6C;
  box-shadow: 0 0 10px rgba(245, 108, 108, 0.3);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(245, 108, 108, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0);
  }
}

.menu-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.menu-item-header h3 {
  margin: 0;
}

.price {
  color: #F56C6C;
  font-weight: bold;
}

.description {
  margin: 10px 0;
  color: #606266;
  font-size: 14px;
}

.menu-item-details {
  display: flex;
  gap: 5px;
  margin: 10px 0 0 0;
}

.empty-menu,
.loading-menu {
  padding: 20px;
  text-align: center;
}

.chat-textarea {
  width: 100%;
  min-height: 120px;
  padding: 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  color: #606266;
  resize: both;
  margin-top: 10px;
}

.chat-textarea:focus {
  outline: none;
  border-color: #409EFF;
}

.chat-section {
  width: 100%;
  overflow: hidden;
}

.chat-response {
  width: 100%;
  overflow: visible;
}
</style> 