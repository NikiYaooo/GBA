<script setup lang="ts">
import { ref, watch } from 'vue'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  loading: boolean
}>()

const emit = defineEmits<{
  createProject: [name: string, description?: string, model?: string]
}>()

const name = ref('')
const description = ref('')
const model = ref('bge-small-zh')

const models = [
  { value: 'bge-small-zh', label: 'BGE Small (快速)' },
  { value: 'bge-large-zh', label: 'BGE Large (精确)' },
  { value: 'text2vec-base', label: 'Text2Vec Base' },
]

watch(() => visible.value, (v) => {
  if (v) {
    name.value = ''
    description.value = ''
    model.value = 'bge-small-zh'
  }
})

const onSubmit = () => {
  if (!name.value.trim()) return
  emit('createProject', name.value.trim(), description.value.trim() || undefined, model.value)
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="新建项目" width="500px" top="20vh">
    <el-form label-width="80px">
      <el-form-item label="项目名称" required>
        <el-input v-model="name" placeholder="输入项目名称" maxlength="50" />
      </el-form-item>
      <el-form-item label="项目描述">
        <el-input v-model="description" type="textarea" :rows="3" placeholder="可选描述" maxlength="200" />
      </el-form-item>
      <el-form-item label="向量模型">
        <el-select v-model="model" class="w-full">
          <el-option v-for="m in models" :key="m.value" :label="m.label" :value="m.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" :disabled="!name.trim()" @click="onSubmit">创建</el-button>
    </template>
  </el-dialog>
</template>
