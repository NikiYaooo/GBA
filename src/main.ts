import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './style.css'
import App from './App.vue'
import router from './router'

// 远程开关：检测到开关关闭时自动退出
let _quitting = false
function handleSwitchOff() {
  if (_quitting) return
  _quitting = true
  ElMessage.warning('软件权限已被远程关闭，3 秒后将退出程序')
  setTimeout(() => {
    ;(window as any).electronAPI?.quitApp()
    // 降级方案：如果 IPC 不可用，强制关闭当前窗口
    window.close()
  }, 3000)
}

// 注册 axios 全局拦截器
import axios from 'axios'

// 响应拦截器：检测远程开关状态
axios.interceptors.response.use(
  (response) => {
    // 功能使用结束前检测：X-Switch-Status: off → 3 秒后关闭
    if (response.headers['x-switch-status'] === 'off') {
      handleSwitchOff()
    }
    return response
  },
  (error) => {
    // 功能使用前检测：403 + 软件权限不足
    if (error.response?.status === 403 && error.response?.data?.message === '软件权限不足') {
      ElMessage.error('软件权限不足')
    }
    return Promise.reject(error)
  },
)

// 监听 Electron IPC 开关拒绝事件
;(window as any).electronAPI?.onSwitchDenied?.((msg: string) => {
  ElMessage.error(msg)
})

// 创建Vue应用实例
const app = createApp(App)
const pinia = createPinia()

// 使用 Pinia
app.use(pinia)
// 使用路由
app.use(router)
// 使用 Element Plus
app.use(ElementPlus)

// 挂载应用
app.mount('#app')
