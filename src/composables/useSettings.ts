import { ref, type Ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/utils/api'
import type { ModelConfig } from '@/types'

export function useSettings(models: Ref<{ name: string; type: 'cloud' | 'local' }[]>) {
  const showSettings = ref(false)
  const autoStart = ref(false)
  const tortoiseSvnPath = ref('')
  const modelConfigs = ref<Record<string, ModelConfig>>({})
  const testingModel = ref('')

  const loadConfig = async () => {
    try {
      const r = await axios.get(apiUrl('/api/config'))
      const cfg: Record<string, ModelConfig> = {}
      const fetched = r.data.success && r.data.data?.models ? r.data.data.models : {}
      models.value.forEach(m => {
        cfg[m.name] = fetched[m.name] || { modelId: '', apiKey: '' }
      })
      modelConfigs.value = cfg
      if (r.data.success && r.data.data?.tortoiseSvnPath) {
        tortoiseSvnPath.value = r.data.data.tortoiseSvnPath
      }
    } catch { /* */ }
  }

  const saveConfig = async () => {
    try {
      await axios.post(apiUrl('/api/config'), {
        models: modelConfigs.value,
        tortoiseSvnPath: tortoiseSvnPath.value
      })
      ElMessage.success('已保存')
    } catch { ElMessage.error('保存失败') }
  }

  const testModel = async (modelName: string) => {
    const api = (window as any).electronAPI
    if (!api?.testAIModel) { ElMessage.warning('仅桌面应用可用'); return }
    const cfg = modelConfigs.value[modelName]
    if (!cfg || !cfg.apiKey) { ElMessage.warning('请先填写 API Key'); return }
    testingModel.value = modelName
    try {
      const r = await api.testAIModel(modelName, cfg.apiKey, cfg.modelId)
      if (r.success) ElMessage.success(`${modelName} 连接成功`)
      else ElMessage.warning(`${modelName} 连接失败: ${r.error || '未知错误'}`)
    } catch (e: any) {
      ElMessage.error('测试失败: ' + (e?.message || String(e)))
    } finally { testingModel.value = '' }
  }

  const handleAutoStartChange = async (val: boolean) => {
    const api = (window as any).electronAPI
    if (api?.toggleAutoStart) {
      autoStart.value = await api.toggleAutoStart(Boolean(val))
    }
  }

  const openSettings = async (loadProfessionsFull?: () => Promise<void>) => {
    if (loadProfessionsFull) await loadProfessionsFull()
    showSettings.value = true
    loadConfig()
  }

  return {
    showSettings, autoStart, tortoiseSvnPath, modelConfigs, testingModel,
    loadConfig, saveConfig, testModel, handleAutoStartChange, openSettings
  }
}
