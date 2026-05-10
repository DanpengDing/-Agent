<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2>知识库管理</h2>
      <p class="subtitle">上传并管理知识库文档</p>
    </div>

    <el-card class="upload-card">
      <template #header>
        <div class="card-header">
          <span>文件上传</span>
        </div>
      </template>

      <div class="upload-area">
        <el-upload
          drag
          action=""
          multiple
          :show-file-list="false"
          :http-request="handleUpload"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到这里，或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 `.txt`、`.md`、`.pdf` 文件
            </div>
          </template>
        </el-upload>
      </div>
    </el-card>

    <div v-if="uploadHistory.length > 0" class="history-section">
      <h3>上传记录</h3>
      <el-table :data="uploadHistory" style="width: 100%">
        <el-table-column prop="fileName" label="文件名" min-width="240" />
        <el-table-column prop="chunks" label="新增切片数" width="140" align="center" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'success' ? 'success' : 'danger'">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="信息" min-width="220" />
        <el-table-column prop="time" label="时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadFile } from '../api/knowledge'

const uploadHistory = ref([])

const handleUpload = async ({ file }) => {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await uploadFile(formData)
    uploadHistory.value.unshift({
      fileName: res.file_name,
      chunks: res.chunks_added,
      status: res.status,
      message: res.message,
      time: new Date().toLocaleString()
    })
    ElMessage.success(`文件 ${file.name} 上传成功`)
  } catch (error) {
    uploadHistory.value.unshift({
      fileName: file.name,
      chunks: 0,
      status: 'error',
      message: error.message || '上传失败',
      time: new Date().toLocaleString()
    })
    ElMessage.error(`文件 ${file.name} 上传失败`)
  }
}
</script>

<style scoped>
.knowledge-page {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background: #f5f7fb;
}

.page-header {
  max-width: 1080px;
  margin: 0 auto 24px;
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

.upload-card,
.history-section {
  max-width: 1080px;
  margin: 0 auto 24px;
}

.upload-area {
  padding: 12px;
}

.history-section h3 {
  margin: 0 0 16px;
  color: #1f2937;
}

:deep(.el-upload-dragger) {
  width: 100%;
}

@media (max-width: 768px) {
  .knowledge-page {
    padding: 16px;
  }
}
</style>
