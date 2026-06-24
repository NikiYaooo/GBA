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

  const showDiagnostics = async () => {
    const api = (window as any).electronAPI
    if (!api?.getBackendDiagnostics) {
      alert('诊断信息不可用')
      return
    }
    try {
      const diag = await api.getBackendDiagnostics()
      const lines = [
        `=== 后端诊断信息 ===`,
        `Python 进程运行中: ${diag.pythonRunning}`,
        `Python 路径: ${diag.pythonPath || '未知'}`,
        `数据目录: ${diag.dataDir || '未知'}`,
        ``,
        `--- main.log (最后 20 行) ---`,
        diag.mainLog || '(空)',
        ``,
        `--- python.log (最后 20 行) ---`,
        diag.pythonLog || '(空)',
      ].join('\n')
      alert(lines)
    } catch (e: any) {
      alert('读取诊断信息失败: ' + (e.message || String(e)))
    }
  }

  setApiBaseUrl(apiBaseUrl.value)

  return { apiBaseUrl, connected, statusText, waitForReady, scanAllPorts, restart, showDiagnostics }
}
