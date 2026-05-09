<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ create: [name: string, type: string] }>()

const draftName = ref('')
const draftType = ref('doc')

const create = () => {
  if (!draftName.value.trim()) { ElMessage.warning('请输入文档名称'); return }
  emit('create', draftName.value.trim(), draftType.value)
  draftName.value = ''
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="新建草稿" width="420px" top="15vh">
    <div class="space-y-4">
      <div>
        <label class="text-sm font-medium text-zinc-700 block mb-2">文档名称</label>
        <el-input v-model="draftName" placeholder="输入名称（无需扩展名）" @keyup.enter="create" />
      </div>
      <div>
        <label class="text-sm font-medium text-zinc-700 block mb-2">文档类型</label>
        <el-radio-group v-model="draftType">
          <el-radio value="doc">文档 (.docx)</el-radio>
          <el-radio value="excel">表格 (.xlsx)</el-radio>
        </el-radio-group>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>
</template>
