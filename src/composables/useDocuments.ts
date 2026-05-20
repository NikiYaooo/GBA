import { ref, computed, type Ref } from 'vue'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import type { DocRecord, ApiResponse } from '@/types'

export function useDocuments(activeCategory: Ref<string>) {
  const docList = ref<DocRecord[]>([])
  const currentDoc = ref<DocRecord>({ id: '', name: '未选择文档', content: '', type: '', path: '', category: '' })
  const searchQuery = ref('')

  const filteredDocList = computed(() => {
    let list = docList.value.filter((d) => (d.category || 'doc') === activeCategory.value)
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      list = list.filter((d) => (d.name || '').toLowerCase().includes(q))
    }
    return list
  })

  const loadDocuments = async (cat?: string) => {
    try {
      const r = await axios.get<ApiResponse<DocRecord[]>>(apiUrl('/api/documents'), {
        params: { category: cat || activeCategory.value }
      })
      if (r.data.success) docList.value = r.data.data || []
    } catch { /* */ }
  }

  const selectDoc = async (doc: DocRecord, onExcelLoad?: (doc: DocRecord) => Promise<void>) => {
    try {
      const r = await axios.get<ApiResponse<DocRecord>>(apiUrl(`/api/documents/${doc.id}`))
      if (r.data.success) {
        currentDoc.value = { ...doc, content: r.data.data?.content || '' }
        const ext = (doc.name || '').split('.').pop()?.toLowerCase() || ''
        if (['xlsx', 'xls'].includes(ext) || doc.category === 'excel') {
          if (onExcelLoad) await onExcelLoad(doc)
        }
      }
    } catch { /* */ }
  }

  const deleteDocument = async (doc: DocRecord) => {
    await axios.delete(apiUrl(`/api/documents/${doc.id}`))
    if (currentDoc.value.id === doc.id) {
      currentDoc.value = { id: '', name: '未选择文档', content: '', type: '', path: '', category: '' }
    }
    await loadDocuments()
  }

  const renameDocument = async (doc: DocRecord, newName: string) => {
    await axios.put(apiUrl(`/api/documents/${doc.id}`), { name: newName.trim() })
    if (currentDoc.value.id === doc.id) currentDoc.value.name = newName.trim()
    await loadDocuments()
  }

  const updateDocument = async (docId: string, data: Record<string, any>) => {
    await axios.put(apiUrl(`/api/documents/${docId}`), data)
  }

  const createDocument = async (name: string, content: string, category: string): Promise<DocRecord | null> => {
    const r = await axios.post<ApiResponse<DocRecord>>(apiUrl('/api/documents/create'), { name, content, category })
    if (r.data.success && r.data.data) {
      docList.value.unshift(r.data.data)
      return r.data.data
    }
    return null
  }

  const uploadFile = async (file: File, category: string): Promise<DocRecord | null> => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    let forceCat = ''
    if (['xlsx', 'xls'].includes(ext)) forceCat = 'excel'
    else if (ext === 'docx' || ext === 'doc') forceCat = 'doc'
    const cat = forceCat || (category === 'draft' ? 'doc' : category)

    const r = await axios.post<ApiResponse<DocRecord>>(apiUrl('/api/documents/upload'), file, {
      headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name), 'X-Category': cat },
      timeout: 120000
    })
    if (r.data.success && r.data.data) {
      // 立即插入到列表头部，无需等待重新请求
      docList.value.unshift(r.data.data)
      return r.data.data
    }
    return null
  }

  return {
    docList, currentDoc, searchQuery, filteredDocList,
    loadDocuments, selectDoc, deleteDocument, renameDocument,
    updateDocument, createDocument, uploadFile
  }
}
