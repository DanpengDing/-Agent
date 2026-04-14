import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: '/api',  // 使用代理路径
  // timeout: 10000,  // 移除超时限制
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    console.log('API请求:', config.method.toUpperCase(), config.url, config.data)
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    console.log('API响应:', response.status, response.data)
    return response.data
  },
  error => {
    console.error('响应错误:', error.response?.status, error.response?.data)
    if (error.response?.status === 500) {
      throw new Error('处理中遇到问题，请稍后再试')
    } else if (error.response?.status === 404) {
      throw new Error('请求的资源不存在')
    } else {
      // 移除超时和服务器不可用的通用提醒
      throw new Error(error.response?.data?.detail || '请求处理中，请稍候...')
    }
  }
)

// 智能对话API
export const chatAPI = {
  // 发送聊天消息
  sendMessage: async (query) => {
    return await api.post('/chat', { query })
  }
}

// 配送查询API
export const deliveryAPI = {
  // 检查配送范围
  checkRange: async (address, travel_mode = 3) => {
    return await api.post('/delivery', { 
      address, 
      travel_mode 
    })
  }
}

// 菜品API
export const menuAPI = {
  // 获取菜品列表
  getMenuList: async () => {
    return await api.get('/menu/list')
  }
}

// 健康检查API
export const healthAPI = {
  // 检查服务状态
  checkHealth: async () => {
    return await api.get('/health')
  }
}

export default api 