<script setup lang="ts">
import { CheckCircle2, Bell } from 'lucide-vue-next'
import type { SVNConfig, NavConfig, Reminder } from '@/types'
import ReminderDialog from './ReminderDialog.vue'

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
  svnOpenAfterUpdate: boolean
  reminders: Reminder[]
  showReminderDialog: boolean
  editingReminder: any
}>()

const emit = defineEmits<{
  'update:newSvnName': [val: string]
  'update:newSvnPath': [val: string]
  'update:newNavName': [val: string]
  'update:newNavPath': [val: string]
  'update:showAddSvnDialog': [val: boolean]
  'update:showAddNavDialog': [val: boolean]
  'update:svnOpenAfterUpdate': [val: boolean]
  'update:showReminderDialog': [val: boolean]
  addSvn: []
  removeSvn: [id: string]
  runSvnUpdate: [item: SVNConfig]
  addNav: []
  removeNav: [id: string]
  openNavItem: [item: NavConfig]
  openReminderDialog: [reminder: any]
  saveReminder: [data: any]
  deleteReminder: [id: string]
}>()

const formatTime = (r: Reminder) => {
  const parts: string[] = []
  if (r.month) parts.push(`${r.month}月`)
  else parts.push('每月')
  if (r.day) parts.push(`${r.day}日`)
  else parts.push('每日')
  parts.push(`${String(r.hour).padStart(2, '0')}:${String(r.minute).padStart(2, '0')}`)
  return parts.join(' ')
}
</script>

<template>
  <el-dialog v-model="visible" title="快捷工具" width="520px" top="8vh">
    <div class="space-y-6">
      <!-- SVN 更新 -->
      <div class="border border-zinc-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-sm">SVN 更新</h3>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-1.5 text-xs text-zinc-500 cursor-pointer select-none" @click.stop>
              <el-checkbox
                :model-value="svnOpenAfterUpdate" size="small"
                @update:model-value="(v: boolean) => emit('update:svnOpenAfterUpdate', v)"
              />更新后打开
            </label>
            <el-button size="small" @click="emit('update:showAddSvnDialog', true)">添加</el-button>
          </div>
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

      <!-- 计划提醒 -->
      <div class="border border-zinc-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-sm">计划提醒</h3>
          <el-button size="small" @click="emit('openReminderDialog', null)">
            <Bell class="w-3.5 h-3.5 mr-1" />添加
          </el-button>
        </div>

        <div v-if="reminders.length === 0" class="text-xs text-zinc-400">暂无提醒</div>
        <div v-for="r in reminders" :key="r.id" class="flex items-center justify-between py-1.5 border-b border-zinc-50 text-sm">
          <div class="flex-1 min-w-0 mr-2">
            <div class="truncate">{{ r.content }}</div>
            <div class="text-xs text-zinc-400">{{ formatTime(r) }}</div>
          </div>
          <div class="flex gap-1 shrink-0">
            <el-button size="small" @click="emit('openReminderDialog', r)">修改</el-button>
            <el-button size="small" type="danger" plain @click="emit('deleteReminder', r.id)">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <ReminderDialog
      :visible="showReminderDialog"
      :edit-reminder="editingReminder"
      @update:visible="(v: boolean) => emit('update:showReminderDialog', v)"
      @save="(data: any) => emit('saveReminder', data)"
    />
  </el-dialog>
</template>
