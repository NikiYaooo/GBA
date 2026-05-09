<script setup lang="ts">
import { CheckCircle2 } from 'lucide-vue-next'
import type { SVNConfig, NavConfig } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

defineProps<{
  svnConfigs: SVNConfig[]
  navConfigs: NavConfig[]
  svnUpdating: string
  showAddSvnDialog: boolean
  showAddNavDialog: boolean
  newSvnName: string
  newSvnPath: string
  newNavName: string
  newNavPath: string
}>()

const emit = defineEmits<{
  'update:newSvnName': [val: string]
  'update:newSvnPath': [val: string]
  'update:newNavName': [val: string]
  'update:newNavPath': [val: string]
  'update:showAddSvnDialog': [val: boolean]
  'update:showAddNavDialog': [val: boolean]
  addSvn: []
  removeSvn: [id: string]
  runSvnUpdate: [item: SVNConfig]
  addNav: []
  removeNav: [id: string]
  openNavItem: [item: NavConfig]
}>()
</script>

<template>
  <el-dialog v-model="visible" title="快捷工具" width="500px" top="8vh">
    <div class="space-y-6">
      <!-- SVN 更新 -->
      <div class="border border-zinc-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-sm">SVN 更新</h3>
          <el-button size="small" @click="emit('update:showAddSvnDialog', true)">添加</el-button>
        </div>

        <el-dialog
          :model-value="showAddSvnDialog" width="400px" top="15vh"
          @update:model-value="(v: boolean) => emit('update:showAddSvnDialog', v)"
        >
          <template #header><span class="text-sm font-semibold">添加 SVN 目录</span></template>
          <div class="space-y-3">
            <el-input
              :model-value="newSvnName" size="small" placeholder="目录名称"
              @update:model-value="(v: string) => emit('update:newSvnName', v)"
            />
            <el-input
              :model-value="newSvnPath" size="small" placeholder="SVN 目录路径"
              @update:model-value="(v: string) => emit('update:newSvnPath', v)"
            >
              <template #suffix>
                <el-button link size="small" @click="emit('addSvn')" style="margin-top:-1px">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>
                </el-button>
              </template>
            </el-input>
          </div>
        </el-dialog>

        <div v-if="svnConfigs.length === 0" class="text-xs text-zinc-400">暂无 SVN 配置</div>
        <div v-for="item in svnConfigs" :key="item.id" class="flex items-center justify-between py-1.5 border-b border-zinc-50 text-sm">
          <span>{{ item.name }}</span>
          <div class="flex gap-1">
            <el-button size="small" :loading="svnUpdating === item.id" @click="emit('runSvnUpdate', item)">更新</el-button>
            <el-button size="small" type="danger" plain @click="emit('removeSvn', item.id)">删除</el-button>
          </div>
        </div>
      </div>

      <!-- 快捷导航 -->
      <div class="border border-zinc-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-sm">快捷导航</h3>
          <el-button size="small" @click="emit('update:showAddNavDialog', true)">添加</el-button>
        </div>

        <el-dialog
          :model-value="showAddNavDialog" width="400px" top="15vh"
          @update:model-value="(v: boolean) => emit('update:showAddNavDialog', v)"
        >
          <template #header><span class="text-sm font-semibold">添加快捷导航</span></template>
          <div class="space-y-3">
            <el-input
              :model-value="newNavName" size="small" placeholder="名称"
              @update:model-value="(v: string) => emit('update:newNavName', v)"
            />
            <el-input
              :model-value="newNavPath" size="small" placeholder="路径或网址"
              @update:model-value="(v: string) => emit('update:newNavPath', v)"
            />
            <el-button type="primary" size="small" @click="emit('addNav')">确认</el-button>
          </div>
        </el-dialog>

        <div v-if="navConfigs.length === 0" class="text-xs text-zinc-400">暂无导航配置</div>
        <div v-for="item in navConfigs" :key="item.id" class="flex items-center justify-between py-1.5 border-b border-zinc-50 text-sm">
          <span>{{ item.name }}</span>
          <div class="flex gap-1">
            <el-button size="small" @click="emit('openNavItem', item)">打开</el-button>
            <el-button size="small" type="danger" plain @click="emit('removeNav', item.id)">删除</el-button>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>
