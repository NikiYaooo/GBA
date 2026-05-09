<script setup lang="ts">
import { FileEdit, Trash2 } from 'lucide-vue-next'
import type { Profession, Role } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

defineProps<{
  professions: Profession[]
  selectedProfession: string
  roles: Role[]
  selectedRole: Role | null
  showAddRoleForm: boolean
  newRoleName: string
  newRolePrompt: string
  editingRole: Role | null
}>()

const emit = defineEmits<{
  'update:selectedProfession': [val: string]
  'update:newRoleName': [val: string]
  'update:newRolePrompt': [val: string]
  selectRole: [role: Role]
  startAddRole: []
  startEditRole: [role: Role]
  deleteRole: [roleId: string]
  saveRole: []
  cancelAddRole: []
  resetDefaults: []
  startCheck: []
}>()
</script>

<template>
  <el-dialog v-model="visible" title="文档质检" width="550px" top="8vh">
    <div class="mb-4">
      <label class="text-sm font-semibold text-app block mb-2">选择职业</label>
      <el-select
        :model-value="selectedProfession" class="w-full"
        @change="(val: string) => emit('update:selectedProfession', val)"
      >
        <el-option v-for="p in professions" :key="p.id" :label="p.name" :value="p.id">
          <div class="flex items-center justify-between">
            <span>{{ p.name }}</span>
            <span class="text-xs text-app-muted">{{ p.role_count }} 个角色</span>
          </div>
        </el-option>
      </el-select>
    </div>

    <div class="mb-3 flex items-center justify-between">
      <label class="text-sm font-semibold text-app">质检角色</label>
      <div class="flex gap-1">
        <el-button size="small" type="primary" plain @click="emit('startAddRole')">新增角色</el-button>
        <el-button size="small" type="warning" plain @click="emit('resetDefaults')">重置默认</el-button>
      </div>
    </div>

    <div v-if="showAddRoleForm" class="border border-blue-200 bg-blue-50 rounded-lg p-3 mb-3">
      <div class="space-y-2">
        <div>
          <label class="text-xs text-app-secondary block mb-1">角色名称</label>
          <el-input
            :model-value="newRoleName" size="small"
            @update:model-value="(v: string) => emit('update:newRoleName', v)"
          />
        </div>
        <div>
          <label class="text-xs text-app-secondary block mb-1">质检提示词</label>
          <el-input
            :model-value="newRolePrompt" type="textarea" :rows="3" size="small"
            @update:model-value="(v: string) => emit('update:newRolePrompt', v)"
          />
        </div>
        <div class="flex gap-2 justify-end">
          <el-button size="small" @click="emit('cancelAddRole')">取消</el-button>
          <el-button size="small" type="primary" @click="emit('saveRole')">
            {{ editingRole ? '更新' : '保存' }}
          </el-button>
        </div>
      </div>
    </div>

    <div class="space-y-2 max-h-[300px] overflow-y-auto">
      <div v-for="role in roles" :key="role.id">
        <div
          :class="['border rounded-lg p-3 cursor-pointer', selectedRole?.id === role.id ? 'border-blue-400 bg-blue-50' : 'border-app hover:border-zinc-300']"
          @click="emit('selectRole', role)"
        >
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-sm">{{ role.name }}</span>
            <div class="flex gap-1">
              <el-button link size="small" @click.stop="emit('startEditRole', role)"><FileEdit class="w-3.5 h-3.5" /></el-button>
              <el-button link size="small" @click.stop="emit('deleteRole', role.id)"><Trash2 class="w-3.5 h-3.5 text-red-400" /></el-button>
            </div>
          </div>
          <p class="text-xs text-app-secondary line-clamp-2">{{ role.prompt }}</p>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!selectedRole" @click="emit('startCheck')">开始质检</el-button>
    </template>
  </el-dialog>
</template>
