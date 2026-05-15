import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl, getErrMsg } from '@/utils/api'

export interface ImageLibRecord {
  id: string
  name: string
  filename: string
  created_at: string
}

export function useImageLibrary() {
  const images = ref<ImageLibRecord[]>([])
  const loading = ref(false)
  const dataUriCache = ref<Record<string, string>>({})

  const loadImages = async () => {
    loading.value = true
    try {
      const r = await axios.get(apiUrl('/api/images/library'))
      if (r.data.success) {
        images.value = r.data.data?.images || []
      }
    } catch { /* */ }
    finally { loading.value = false }
  }

  const getImageData = async (id: string): Promise<string> => {
    if (dataUriCache.value[id]) return dataUriCache.value[id]
    try {
      const r = await axios.get(apiUrl(`/api/images/library/${id}/data`))
      if (r.data.success && r.data.data?.data_uri) {
        dataUriCache.value[id] = r.data.data.data_uri
        return r.data.data.data_uri
      }
    } catch { /* */ }
    return ''
  }

  const saveImage = async (dataUri: string, name: string): Promise<boolean> => {
    try {
      const r = await axios.post(apiUrl('/api/images/library'), { data_uri: dataUri, name })
      if (r.data.success) {
        ElMessage.success('已保存到图片库')
        await loadImages()
        return true
      }
      ElMessage.warning(r.data.message || '保存失败')
    } catch (e: any) {
      ElMessage.error('保存失败: ' + getErrMsg(e))
    }
    return false
  }

  const renameImage = async (id: string, name: string): Promise<boolean> => {
    try {
      const r = await axios.put(apiUrl(`/api/images/library/${id}`), { name })
      if (r.data.success) {
        ElMessage.success('已重命名')
        await loadImages()
        return true
      }
      ElMessage.warning(r.data.message || '重命名失败')
    } catch (e: any) {
      ElMessage.error('重命名失败: ' + getErrMsg(e))
    }
    return false
  }

  const deleteImage = async (id: string): Promise<boolean> => {
    try {
      const r = await axios.delete(apiUrl(`/api/images/library/${id}`))
      if (r.data.success) {
        ElMessage.success('已删除')
        delete dataUriCache.value[id]
        await loadImages()
        return true
      }
      ElMessage.warning(r.data.message || '删除失败')
    } catch (e: any) {
      ElMessage.error('删除失败: ' + getErrMsg(e))
    }
    return false
  }

  return {
    images, loading,
    loadImages, getImageData, saveImage, renameImage, deleteImage,
  }
}
