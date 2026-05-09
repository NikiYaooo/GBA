import { ref } from 'vue'
import axios from 'axios'
import { apiUrl, setApiBaseUrl, scanPorts } from '@/utils/api'

export function useBackend() {
  const apiBaseUrl = ref('http://127.0.0.1:8000')
  const connected = ref(false)
  const statusText = ref('后端服务连接中...')
  let scanning = false

  const waitForReady = async (max = 20) => {
    connected.value = false
    statusText.value = '后端服务连接中...'

    const api = (window as any).electronAPI
    if (api?.getBackendBaseUrl) {
      try { apiBaseUrl.value = await api.getBackendBaseUrl() } catch { /* */ }
    }

    for (let i = 1; i <= max; i++) {
      try {
        await axios.get(apiUrl('/'), { timeout: 3000 })
        connected.value = true
        statusText.value = `后端服务已连接（${apiBaseUrl.value}）`
        setApiBaseUrl(apiBaseUrl.value)
        return true
      } catch {
        if (i % 4 === 0) {
          const found = await scanAllPorts()
          if (found) {
            connected.value = true
            statusText.value = `后端服务已连接（${apiBaseUrl.value}）`
            return true
          }
        }
        statusText.value = `后端服务连接中...（重试 ${i}/${max}）`
        await new Promise(r => setTimeout(r, 2000))
      }
    }
    statusText.value = '后端服务连接失败'
    return false
  }

  const scanAllPorts = async () => {
    if (scanning) return false
    scanning = true
    const found = await scanPorts(apiBaseUrl.value)
    if (found) {
      apiBaseUrl.value = found
      connected.value = true
      statusText.value = `后端服务已连接（${apiBaseUrl.value}）`
      setApiBaseUrl(found)
    }
    scanning = false
    return !!found
  }

  const restart = async () => {
    const api = (window as any).electronAPI
    if (!api?.restartBackend) return
    connected.value = false
    statusText.value = '重启中...'
    await api.restartBackend()
    await waitForReady()
  }

  setApiBaseUrl(apiBaseUrl.value)

  return { apiBaseUrl, connected, statusText, waitForReady, scanAllPorts, restart }
}
