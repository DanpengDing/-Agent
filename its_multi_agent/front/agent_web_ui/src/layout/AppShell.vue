<template>
  <div class="shell">
    <header class="shell-nav">
      <div class="shell-brand">
        <img src="/its-logo.svg" alt="ITS" width="28" height="28" />
        <span>ITS Multi Agent</span>
      </div>
      <nav class="shell-links">
        <RouterLink to="/chat" class="shell-link" :class="{ active: route.path === '/chat' }">
          对话
        </RouterLink>
        <RouterLink to="/knowledge" class="shell-link" :class="{ active: route.path === '/knowledge' }">
          知识库上传
        </RouterLink>
      </nav>
    </header>

    <main class="shell-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRoute, RouterLink } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-main);
}

.shell-nav {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}

.shell-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}

.shell-brand img {
  border-radius: 8px;
}

.shell-links {
  display: flex;
  align-items: center;
  gap: 8px;
}

.shell-link {
  padding: 8px 14px;
  border-radius: 9999px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}

.shell-link:hover {
  background: var(--bg-hover);
  color: var(--text-main);
}

.shell-link.active {
  background: rgba(0, 122, 255, 0.12);
  color: var(--primary);
}

.shell-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 768px) {
  .shell-nav {
    height: auto;
    padding: 12px 16px;
    align-items: flex-start;
    flex-direction: column;
  }

  .shell-links {
    width: 100%;
  }

  .shell-link {
    flex: 1;
    text-align: center;
  }
}
</style>
