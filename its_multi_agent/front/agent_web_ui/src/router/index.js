import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layout/AppShell.vue'

const routes = [
  {
    path: '/',
    component: AppShell,
    redirect: '/chat',
    children: [
      {
        path: 'chat',
        name: 'chat',
        component: () => import('../views/ChatPage.vue')
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgePage.vue')
      },
      {
        path: 'memory',
        name: 'memory',
        component: () => import('../views/MemoryPage.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
