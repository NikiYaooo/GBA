<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ insert: [src: string] }>()

const imageUrl = ref('')

const confirmInsert = () => {
  const url = imageUrl.value.trim()
  if (url) {
    emit('insert', url)
    imageUrl.value = ''
    visible.value = false
  }
}

const insertLocalImage = async () => {
  const api = (window as any).electronAPI
  if (!api?.selectLocalImage) { ElMessage.warning('仅桌面应用可用'); return }
  const result = await api.selectLocalImage()
  if (result?.success && result.dataUri) {
    emit('insert', result.dataUri)
    visible.value = false
  } else if (result?.error && result.error !== 'Canceled') {
    ElMessage.warning(result.error)
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="插入图片" width="420px" top="20vh">
    <div class="space-y-3">
      <el-input v-model="imageUrl" placeholder="输入图片 URL" @keyup.enter="confirmInsert" />
      <div class="flex gap-2">
        <el-button type="primary" :disabled="!imageUrl.trim()" @click="confirmInsert">插入 URL</el-button>
        <el-button @click="insertLocalImage">选择本地图片</el-button>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
    </template>
  </el-dialog>
</template>
