import { ref } from 'vue'
import axios from 'axios'
import { apiUrl } from '@/utils/api'

export function useTheme() {
  const isDark = ref(false)

  // 从 localStorage 初始化
  const saved = localStorage.getItem('app-theme')
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }

  const toggle = () => {
    isDark.value = !isDark.value
    apply()
    saveToConfig(isDark.value)
  }

  const apply = () => {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('app-theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('app-theme', 'light')
    }
  }

  const saveToConfig = async (dark: boolean) => {
    try {
      const r = await axios.get(apiUrl('/api/config'))
      const config = r.data.success ? (r.data.data || {}) : {}
      config.darkMode = dark
      await axios.post(apiUrl('/api/config'), config)
    } catch { /* */ }
  }

  const loadFromConfig = async () => {
    try {
      const r = await axios.get(apiUrl('/api/config'))
      if (r.data.success && r.data.data?.darkMode === true) {
        isDark.value = true
        apply()
      }
    } catch { /* */ }
  }

  return { isDark, toggle, apply, loadFromConfig }
}
