import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { KBStats, ApiResponse, KBProject, KBFolder, KBDocumentV2, KBSearchResult, KBBackup } from '@/types'

export interface ScannedFile {
  name: string
  path: string
  size: number
  ext: string
}

export interface ImportProgress {
  status: 'pending' | 'scanning' | 'importing' | 'paused' | 'done' | 'error' | 'cancelled'
  progress: number
  message: string
  total_files: number
  processed_files: number
  current_file: string
  succeeded_files?: number
  skipped_files?: number
  skip_reasons?: Record<string, number>
}

export function useKnowledgeBase() {
  // === 对话框状态 ===
  const showKB = ref(false)
  const isUploadingKB = ref(false)
  const showChunkSizeDialog = ref(false)

  // === 数据状态 ===
  const projects = ref<KBProject[]>([])
  const activeProjectId = ref('')
  const folders = ref<KBFolder[]>([])
  const documents = ref<KBDocumentV2[]>([])
  const kbStats = ref<KBStats>({ total_documents: 0, total_chunks: 0, total_size_bytes: 0, vector_count: 0, documents: [] })
  const searchResults = ref<KBSearchResult[]>([])
  const backups = ref<KBBackup[]>([])
  const vocabList = ref<string[]>([])
  const chunkSizeMin = ref(100)
  const chunkSizeMax = ref(500)

  // === 加载状态 ===
  const loading = ref(false)
  const searchLoading = ref(false)

  // ========== 项目管理 ==========

  const loadProjects = async () => {
    try {
      const r = await axios.get(apiUrl('/api/kb/projects'))
      if (r.data.success && r.data.data) {
        projects.value = r.data.data.projects || []
        activeProjectId.value = r.data.data.active_project_id || ''
      }
    } catch { /* */ }
  }

  const createProject = async (name: string, description: string = '', model: string = 'bge-small-zh') => {
    try {
      const r = await axios.post(apiUrl('/api/kb/project'), { name, description, embedding_model: model })
      if (r.data.success) {
        await loadProjects()
        if (r.data.data?.id) activeProjectId.value = r.data.data.id
        ElMessage.success('项目已创建')
        return true
      }
      ElMessage.warning(r.data.message || '创建失败')
      return false
    } catch (e: any) {
      ElMessage.error('创建失败: ' + getErrMsg(e))
      return false
    }
  }

  const deleteProject = async (id: string) => {
    try {
      const r = await axios.delete(apiUrl(`/api/kb/project/${id}`))
      if (r.data.success) {
        await loadProjects()
        ElMessage.success('项目已删除')
        return true
      }
      return false
    } catch (e: any) {
      ElMessage.error('删除失败: ' + getErrMsg(e))
      return false
    }
  }

  const switchProject = async (id: string) => {
    try {
      const r = await axios.post(apiUrl(`/api/kb/project/${id}/activate`))
      if (r.data.success) {
        activeProjectId.value = id
        await Promise.all([loadFolders(), loadDocuments(), loadStats()])
      }
    } catch { /* */ }
  }

  // ========== 文件夹管理 ==========

  const loadFolders = async () => {
    if (!activeProjectId.value) { folders.value = []; return }
    try {
      const r = await axios.get(apiUrl(`/api/kb/project/${activeProjectId.value}/folders`))
      if (r.data.success) folders.value = r.data.data?.folders || []
    } catch { folders.value = [] }
  }

  const createFolder = async (name: string) => {
    if (!activeProjectId.value) { ElMessage.warning('请先选择项目'); return false }
    try {
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/folder`), { name })
      if (r.data.success) { await loadFolders(); return true }
      ElMessage.warning(r.data.message || '创建失败')
      return false
    } catch { ElMessage.error('创建文件夹失败'); return false }
  }

  const renameFolder = async (folderId: string, name: string) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.put(apiUrl(`/api/kb/project/${activeProjectId.value}/folder/${folderId}`), { name })
      if (r.data.success) { await loadFolders(); return true }
      return false
    } catch { return false }
  }

  const deleteFolder = async (folderId: string) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.delete(apiUrl(`/api/kb/project/${activeProjectId.value}/folder/${folderId}`))
      if (r.data.success) { await loadFolders(); await loadDocuments(); return true }
      return false
    } catch { return false }
  }

  // ========== 文档管理 ==========

  const loadDocuments = async (folderId?: string) => {
    if (!activeProjectId.value) { documents.value = []; return }
    try {
      const params = folderId ? `?folder_id=${folderId}` : ''
      const r = await axios.get(apiUrl(`/api/kb/project/${activeProjectId.value}/documents${params}`))
      if (r.data.success) documents.value = r.data.data?.documents || []
    } catch { documents.value = [] }
  }

  const uploadFile = async (file: File, folderId?: string) => {
    isUploadingKB.value = true
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/octet-stream',
        'X-Filename': encodeURIComponent(file.name),
      }
      if (folderId) headers['X-Folder-Id'] = folderId
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/upload`), file, { headers, timeout: 120000 })
      if (r.data.success) { await loadDocuments(); return true }
      ElMessage.warning(r.data.message || '上传失败')
      return false
    } catch (e: any) { ElMessage.error('上传失败: ' + getErrMsg(e)); return false }
    finally { isUploadingKB.value = false }
  }

  const updateDocument = async (docId: string, updates: Record<string, any>) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.put(apiUrl(`/api/kb/project/${activeProjectId.value}/doc/${docId}`), updates)
      if (r.data.success) { await loadDocuments(); return true }
      return false
    } catch { return false }
  }

  const deleteDocument = async (docId: string) => {
    if (!activeProjectId.value) return
    await axios.delete(apiUrl(`/api/kb/project/${activeProjectId.value}/doc/${docId}`))
    await loadDocuments()
  }

  const clearAll = async () => {
    // v2.6.2: clear all docs in active project
    if (!activeProjectId.value) return
    for (const d of documents.value) {
      await axios.delete(apiUrl(`/api/kb/project/${activeProjectId.value}/doc/${d.id}`))
    }
    await loadDocuments()
  }

  // ========== 检索 ==========

  const search = async (query: string, topK: number = 5, folderId?: string) => {
    if (!activeProjectId.value || !query) { searchResults.value = []; return }
    searchLoading.value = true
    try {
      const body: Record<string, any> = { query, top_k: topK }
      if (folderId) body.folder_id = folderId
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/search`), body)
      if (r.data.success) searchResults.value = r.data.data?.results || []
      else searchResults.value = []
    } catch { searchResults.value = [] }
    finally { searchLoading.value = false }
  }

  const fuzzySearch = async (keyword: string, folderId?: string) => {
    if (!activeProjectId.value || !keyword) { searchResults.value = []; return }
    searchLoading.value = true
    try {
      const body: Record<string, any> = { keyword }
      if (folderId) body.folder_id = folderId
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/fuzzy-search`), body)
      if (r.data.success) searchResults.value = r.data.data?.results || []
      else searchResults.value = []
    } catch { searchResults.value = [] }
    finally { searchLoading.value = false }
  }

  // ========== 备份 ==========

  const loadBackups = async () => {
    if (!activeProjectId.value) { backups.value = []; return }
    try {
      const r = await axios.get(apiUrl(`/api/kb/project/${activeProjectId.value}/backups`))
      if (r.data.success) backups.value = r.data.data?.backups || []
    } catch { backups.value = [] }
  }

  const createBackup = async () => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/backup`))
      if (r.data.success) { await loadBackups(); ElMessage.success('备份已创建'); return true }
      ElMessage.warning(r.data.message || '备份失败')
      return false
    } catch { ElMessage.error('创建备份失败'); return false }
  }

  const restoreBackup = async (filename: string) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/restore`), { filename })
      if (r.data.success) {
        await Promise.all([loadDocuments(), loadFolders(), loadStats()])
        ElMessage.success('备份已恢复')
        return true
      }
      ElMessage.warning(r.data.message || '恢复失败')
      return false
    } catch { ElMessage.error('恢复备份失败'); return false }
  }

  // ========== 自定义词库 ==========

  const loadVocab = async () => {
    if (!activeProjectId.value) { vocabList.value = []; return }
    try {
      const r = await axios.get(apiUrl(`/api/kb/project/${activeProjectId.value}/vocab`))
      if (r.data.success) vocabList.value = r.data.data?.vocab || []
    } catch { vocabList.value = [] }
  }

  const addVocab = async (word: string) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.post(apiUrl(`/api/kb/project/${activeProjectId.value}/vocab`), { word })
      if (r.data.success) { await loadVocab(); return true }
      ElMessage.warning(r.data.message || '添加失败')
      return false
    } catch { ElMessage.error('添加失败'); return false }
  }

  const removeVocab = async (word: string) => {
    if (!activeProjectId.value) return false
    try {
      const r = await axios.delete(apiUrl(`/api/kb/project/${activeProjectId.value}/vocab/${encodeURIComponent(word)}`))
      if (r.data.success) { await loadVocab(); return true }
      return false
    } catch { return false }
  }

  // ========== 统计（兼容旧接口） ==========

  const loadStats = async () => {
    try {
      const r = await axios.get(apiUrl('/api/kb/stats'))
      if (r.data.success && r.data.data) {
        kbStats.value = r.data.data
      }
    } catch { /* */ }
  }

  const openKB = () => {
    showKB.value = true
    loadProjects().then(() => {
      loadFolders()
      loadDocuments()
      loadStats()
    })
  }

  // ========== 兼容旧接口属性 ==========

  const folderPath = ref('')
  const scannedFiles = ref<any[]>([])
  const selectedFiles = ref<Set<string>>(new Set())
  const isScanning = ref(false)
  const importProgress = ref<any>(null)
  const isImporting = ref(false)
  const isPaused = ref(false)

  const scanFolder = async () => { /* no-op in v2.6.2 */ }
  const importFolder = async () => { /* no-op in v2.6.2 */ }
  const toggleFile = (path: string) => { /* no-op */ }
  const selectAllFiles = () => { /* no-op */ }
  const deselectAllFiles = () => { /* no-op */ }
  const selectFilesByType = (ext: string) => { /* no-op */ }
  const deselectFilesByType = (ext: string) => { /* no-op */ }
  const toggleFilesByType = (ext: string) => { /* no-op */ }
  const pauseImport = async () => { /* no-op */ }
  const resumeImport = async () => { /* no-op */ }
  const stopImport = async () => { /* no-op */ }
  const resetFolderImport = () => { /* no-op */ }
  const stopPolling = () => { /* no-op */ }
  const saveChunkSize = async () => { /* no-op */ }
  const rechunk = async () => { /* no-op */ }

  return {
    // 状态
    showKB, isUploadingKB, showChunkSizeDialog,
    projects, activeProjectId, folders, documents,
    kbStats, searchResults, backups, vocabList,
    chunkSizeMin, chunkSizeMax, loading, searchLoading,

    // 项目管理
    loadProjects, createProject, deleteProject, switchProject,

    // 文件夹
    loadFolders, createFolder, renameFolder, deleteFolder,

    // 文档
    loadDocuments, uploadFile, updateDocument, deleteDocument, clearAll,

    // 检索
    search, fuzzySearch,

    // 备份
    loadBackups, createBackup, restoreBackup,

    // 词库
    loadVocab, addVocab, removeVocab,

    // 旧接口兼容
    loadStats, openKB,
    folderPath, scannedFiles, selectedFiles, isScanning, importProgress,
    isImporting, isPaused,
    scanFolder, importFolder, toggleFile, selectAllFiles, deselectAllFiles,
    selectFilesByType, deselectFilesByType, toggleFilesByType,
    pauseImport, resumeImport, stopImport, resetFolderImport, stopPolling,
    saveChunkSize, rechunk,
  }
}
