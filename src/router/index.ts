import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'

// 定义路由配置
const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage,
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHashHistory(), // Electron环境下必须使用 Hash 路由，否则打包后白屏
  routes,
})

export default router
