import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { KBStats, ApiResponse } from '@/types'

export interface ScannedFile {
  name: string
  path: string
  size: number
  ext: string
}

export interface ImportProgress {
  status: 'pending' | 'scanning' | 'importing' | 'done' | 'error' | 'cancelled'
  progress: number
  message: string
  total_files: number
  processed_files: number
  current_file: string
}

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

  // 文件夹导入相关
  const folderPath = ref('')
  const scannedFiles = ref<ScannedFile[]>([])
  const isScanning = ref(false)
  const importProgress = ref<ImportProgress | null>(null)
  const isImporting = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

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

  const openKB = () => { showKB.value = true; loadStats(); resetFolderImport() }

  const scanFolder = async () => {
    const path = folderPath.value.trim()
    if (!path) { ElMessage.warning('请输入文件夹路径'); return }
    isScanning.value = true
    scannedFiles.value = []
    try {
      const r = await axios.post(apiUrl('/api/kb/scan-folder'), { path })
      if (r.data.success) {
        scannedFiles.value = r.data.data.files || []
        if (scannedFiles.value.length === 0) {
          ElMessage.info('文件夹中没有找到支持的文档')
        }
      } else {
        ElMessage.warning(r.data.message || '扫描失败')
      }
    } catch (e: any) {
      ElMessage.error('扫描失败: ' + getErrMsg(e))
    } finally {
      isScanning.value = false
    }
  }

  const importFolder = async () => {
    const path = folderPath.value.trim()
    if (!path) { ElMessage.warning('请输入文件夹路径'); return }
    if (scannedFiles.value.length === 0) { ElMessage.warning('请先扫描文件夹'); return }

    isImporting.value = true
    importProgress.value = { status: 'pending', progress: 0, message: '启动中...', total_files: 0, processed_files: 0, current_file: '' }

    try {
      const r = await axios.post(apiUrl('/api/kb/import-folder'), { path })
      if (!r.data.success || !r.data.data?.task_id) {
        ElMessage.warning(r.data.message || '启动导入失败')
        isImporting.value = false
        return
      }
      const taskId = r.data.data.task_id
      startPolling(taskId)
    } catch (e: any) {
      ElMessage.error('启动导入失败: ' + getErrMsg(e))
      isImporting.value = false
    }
  }

  const startPolling = (taskId: string) => {
    stopPolling()
    pollTimer = setInterval(async () => {
      try {
        const r = await axios.get(apiUrl(`/api/kb/import-progress/${taskId}`))
        if (r.data.success && r.data.data) {
          importProgress.value = r.data.data as ImportProgress
          const st = r.data.data.status
          if (st === 'done') {
            stopPolling()
            isImporting.value = false
            ElMessage.success(r.data.data.message || '导入完成')
            await loadStats()
          } else if (st === 'error') {
            stopPolling()
            isImporting.value = false
            ElMessage.error(r.data.data.message || '导入失败')
          } else if (st === 'cancelled') {
            stopPolling()
            isImporting.value = false
          }
        }
      } catch {
        stopPolling()
        isImporting.value = false
      }
    }, 500)
  }

  const stopPolling = () => {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  }

  const resetFolderImport = () => {
    stopPolling()
    folderPath.value = ''
    scannedFiles.value = []
    importProgress.value = null
    isImporting.value = false
    isScanning.value = false
  }

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
    saveChunkSize, rechunk, deleteDocument, clearAll,
    folderPath, scannedFiles, isScanning, importProgress, isImporting,
    scanFolder, importFolder, resetFolderImport, stopPolling,
  }
}
