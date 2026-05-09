import { ref } from 'vue'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { KBStats, ApiResponse } from '@/types'

export function useKnowledgeBase() {
  const showKB = ref(false)
  const isUploadingKB = ref(false)
  const kbStats = ref<KBStats>({
    total_documents: 0, total_chunks: 0, total_size_bytes: 0,
    vector_count: 0, documents: []
  })
  const chunkSize = ref(512)
  const showChunkSizeDialog = ref(false)

  const loadStats = async () => {
    try {
      const r = await axios.get<ApiResponse<KBStats>>(apiUrl('/api/kb/stats'))
      if (r.data.success && r.data.data) {
        kbStats.value = r.data.data
        chunkSize.value = r.data.data.chunk_size || 512
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
    const r = await axios.post(apiUrl('/api/kb/chunk-size'), { size: chunkSize.value })
    if (r.data.success) { showChunkSizeDialog.value = false; await loadStats() }
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
    showKB, isUploadingKB, kbStats, chunkSize, showChunkSizeDialog,
    loadStats, openKB, uploadFile, saveChunkSize, deleteDocument, clearAll
  }
}
