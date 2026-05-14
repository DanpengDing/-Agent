<template>
  <div class="memory-page">
    <div class="page-header">
      <div>
        <h2>记忆管理</h2>
        <p class="subtitle">查看长期记忆与用户偏好，并支持手动维护偏好项。</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="userId"
          placeholder="请输入用户 ID"
          class="user-id-input"
          clearable
          @keyup.enter="refreshAll"
        />
        <el-button type="primary" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="24" class="content-grid">
      <el-col :xs="24" :lg="12">
        <el-card class="memory-card">
          <template #header>
            <div class="card-header">
              <span>长期记忆</span>
              <el-tag type="info">{{ longTermMemories.length }} 条</el-tag>
            </div>
          </template>

          <el-empty v-if="!loadingLongTerm && longTermMemories.length === 0" description="暂无长期记忆" />

          <el-table v-else v-loading="loadingLongTerm" :data="longTermMemories" style="width: 100%">
            <el-table-column prop="memory_key" label="键" min-width="180" />
            <el-table-column prop="memory_value" label="值" min-width="220" />
            <el-table-column prop="memory_type" label="类型" width="120" />
            <el-table-column prop="updated_at" label="更新时间" min-width="180" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card class="memory-card">
          <template #header>
            <div class="card-header">
              <span>用户偏好</span>
              <el-tag type="success">{{ preferences.length }} 条</el-tag>
            </div>
          </template>

          <el-form :inline="true" class="preference-form" @submit.prevent>
            <el-form-item>
              <el-input v-model="preferenceForm.preference_key" placeholder="偏好键，如 reply.style" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="preferenceForm.preference_value" placeholder="偏好值，如 简洁" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSavePreference">保存偏好</el-button>
            </el-form-item>
          </el-form>

          <el-empty v-if="!loadingPreferences && preferences.length === 0" description="暂无用户偏好" />

          <el-table v-else v-loading="loadingPreferences" :data="preferences" style="width: 100%">
            <el-table-column prop="memory_key" label="键" min-width="180" />
            <el-table-column prop="memory_value" label="值" min-width="200" />
            <el-table-column prop="memory_type" label="类型" width="120" />
            <el-table-column prop="updated_at" label="更新时间" min-width="180" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="scope">
                <el-button link type="danger" @click="handleDeletePreference(scope.row.memory_key)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="24">
        <el-card class="memory-card">
          <template #header>
            <div class="card-header">
              <span>任务状态记忆</span>
              <div class="task-header-tags">
                <el-tag v-if="activeTask" type="warning">当前活跃任务：{{ activeTask.task_type }}</el-tag>
                <el-tag type="info">{{ taskMemories.length }} 条</el-tag>
              </div>
            </div>
          </template>

          <el-empty v-if="!loadingTasks && taskMemories.length === 0" description="暂无任务状态记忆" />

          <el-table v-else v-loading="loadingTasks" :data="taskMemories" style="width: 100%">
            <el-table-column prop="task_type" label="任务类型" min-width="160" />
            <el-table-column prop="task_status" label="状态" width="140" />
            <el-table-column prop="task_stage" label="阶段" min-width="160" />
            <el-table-column prop="task_goal" label="任务目标" min-width="220" show-overflow-tooltip />
            <el-table-column prop="last_error" label="最近错误" min-width="220" show-overflow-tooltip />
            <el-table-column prop="last_active_at" label="最近活跃时间" min-width="180" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  deleteUserPreference,
  getActiveTask,
  getLongTermMemories,
  getTaskMemories,
  getUserPreferences,
  upsertUserPreference
} from '../api/memory'

const userId = ref(localStorage.getItem('currentUserId') || 'root1')
const longTermMemories = ref([])
const preferences = ref([])
const taskMemories = ref([])
const activeTask = ref(null)
const loadingLongTerm = ref(false)
const loadingPreferences = ref(false)
const loadingTasks = ref(false)
const preferenceForm = reactive({
  preference_key: '',
  preference_value: ''
})

const ensureUserId = () => {
  const normalized = (userId.value || '').trim()
  if (!normalized) {
    ElMessage.warning('请先输入用户 ID')
    return ''
  }
  userId.value = normalized
  return normalized
}

const refreshLongTermMemories = async () => {
  const normalizedUserId = ensureUserId()
  if (!normalizedUserId) return
  loadingLongTerm.value = true
  try {
    const res = await getLongTermMemories(normalizedUserId)
    longTermMemories.value = res.items || []
  } catch (error) {
    ElMessage.error(error.message || '获取长期记忆失败')
  } finally {
    loadingLongTerm.value = false
  }
}

const refreshPreferences = async () => {
  const normalizedUserId = ensureUserId()
  if (!normalizedUserId) return
  loadingPreferences.value = true
  try {
    const res = await getUserPreferences(normalizedUserId)
    preferences.value = res.items || []
  } catch (error) {
    ElMessage.error(error.message || '获取用户偏好失败')
  } finally {
    loadingPreferences.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([refreshLongTermMemories(), refreshPreferences(), refreshTasks()])
}

const refreshTasks = async () => {
  const normalizedUserId = ensureUserId()
  if (!normalizedUserId) return
  loadingTasks.value = true
  try {
    const [listRes, activeRes] = await Promise.all([
      getTaskMemories(normalizedUserId),
      getActiveTask(normalizedUserId)
    ])
    taskMemories.value = listRes.items || []
    activeTask.value = activeRes.item || null
  } catch (error) {
    ElMessage.error(error.message || '获取任务状态失败')
  } finally {
    loadingTasks.value = false
  }
}

const handleSavePreference = async () => {
  const normalizedUserId = ensureUserId()
  if (!normalizedUserId) return
  if (!preferenceForm.preference_key.trim() || !preferenceForm.preference_value.trim()) {
    ElMessage.warning('请填写完整的偏好键和值')
    return
  }

  try {
    await upsertUserPreference({
      user_id: normalizedUserId,
      preference_key: preferenceForm.preference_key.trim(),
      preference_value: preferenceForm.preference_value.trim(),
      session_id: ''
    })
    ElMessage.success('偏好已保存')
    preferenceForm.preference_key = ''
    preferenceForm.preference_value = ''
    await refreshPreferences()
  } catch (error) {
    ElMessage.error(error.message || '保存偏好失败')
  }
}

const handleDeletePreference = async (preferenceKey) => {
  const normalizedUserId = ensureUserId()
  if (!normalizedUserId) return
  try {
    await deleteUserPreference(normalizedUserId, preferenceKey)
    ElMessage.success('偏好已删除')
    await refreshPreferences()
  } catch (error) {
    ElMessage.error(error.message || '删除偏好失败')
  }
}

refreshAll()
</script>

<style scoped>
.memory-page {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background: #f5f7fb;
}

.page-header {
  max-width: 1200px;
  margin: 0 auto 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-header h2 {
  margin: 0 0 8px;
  color: #1f2937;
}

.subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-id-input {
  width: 220px;
}

.content-grid {
  max-width: 1200px;
  margin: 0 auto;
}

.memory-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preference-form {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .memory-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .user-id-input {
    width: 100%;
  }
}
</style>
