import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { KBStats, ApiResponse } from '@/types'

export function useKnowledgeBase() {
  const showKB = ref(false)
  const isUploadingKB = ref(false)
  const kbStats = ref<KBStats>({
    total_documents: 0, total_chunks: 0, total_size_bytes: 0,
    vector_count: 0, documents: []
  })
  const chunkSizeMin = ref(100)
  const chunkSizeMax = ref(500)
  const showChunkSizeDialog = ref(false)

  const loadStats = async () => {
    try {
      const r = await axios.get<ApiResponse<KBStats>>(apiUrl('/api/kb/stats'))
      if (r.data.success && r.data.data) {
        kbStats.value = r.data.data
        chunkSizeMin.value = r.data.data.chunk_size_min || 100
        chunkSizeMax.value = r.data.data.chunk_size_max || 500
      }
    } catch { /* */ }
  }

  const openKB = () => { showKB.value = true; loadStats() }

  const uploadFile = async (file: File) => {
    isUploadingKB.value = true
    try {
      const r = await axios.post(apiUrl('/api/kb/upload'), file, {
        headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) },
        timeout: 120000
      })
      if (r.data.success) { await loadStats(); return true }
      return false
    } finally { isUploadingKB.value = false }
  }

  const saveChunkSize = async () => {
    try {
      const r = await axios.post(apiUrl('/api/kb/chunk-size'), {
        min: chunkSizeMin.value,
        max: chunkSizeMax.value
      })
      if (r.data.success) {
        // 保存后触发重新分块
        await rechunk()
        showChunkSizeDialog.value = false
        await loadStats()
      }
    } catch { ElMessage.error('保存失败') }
  }

  const rechunk = async () => {
    try {
      const r = await axios.post(apiUrl('/api/kb/rechunk'))
      if (r.data.success) {
        ElMessage.success('知识库已按新区间重新分块')
      } else {
        ElMessage.warning(r.data.message || '重新分块完成')
      }
    } catch { ElMessage.error('重新分块失败') }
  }

  const deleteDocument = async (fileHash: string) => {
    await axios.delete(apiUrl(`/api/kb/document/${fileHash}`))
    await loadStats()
  }

  const clearAll = async () => {
    await axios.post(apiUrl('/api/kb/clear'))
    await loadStats()
  }

  return {
    showKB, isUploadingKB, kbStats, chunkSizeMin, chunkSizeMax,
    showChunkSizeDialog, loadStats, openKB, uploadFile,
    saveChunkSize, rechunk, deleteDocument, clearAll
  }
}
