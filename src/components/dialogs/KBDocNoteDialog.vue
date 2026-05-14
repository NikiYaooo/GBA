<script setup lang="ts">
import { ref, watch } from 'vue'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  docId: string
  currentNote: string
}>()

const emit = defineEmits<{
  save: [docId: string, note: string]
}>()

const note = ref('')

watch(() => props.docId, () => {
  note.value = props.currentNote || ''
})

watch(() => visible.value, (v) => {
  if (v) {
    note.value = props.currentNote || ''
  }
})

const onSave = () => {
  emit('save', props.docId, note.value)
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="文档备注" width="420px" top="25vh">
    <el-input
      v-model="note"
      type="textarea"
      :rows="5"
      placeholder="添加备注信息..."
      maxlength="500"
      show-word-limit
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>
