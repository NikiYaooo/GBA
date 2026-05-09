import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './style.css'
import App from './App.vue'
import router from './router'

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
