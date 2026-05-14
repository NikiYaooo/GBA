<script setup lang="ts">
import { ref } from 'vue'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  vocabList: string[]
  loading: boolean
}>()

const emit = defineEmits<{
  loadVocab: []
  addVocab: [word: string]
  removeVocab: [word: string]
}>()

const newWord = ref('')

const onOpen = () => {
  emit('loadVocab')
}

const onAdd = () => {
  const word = newWord.value.trim()
  if (!word || props.vocabList.includes(word)) return
  emit('addVocab', word)
  newWord.value = ''
}

const onRemove = (word: string) => {
  emit('removeVocab', word)
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="自定义词库"
    width="450px"
    top="18vh"
    @open="onOpen"
  >
    <div class="flex gap-2 mb-4">
      <el-input
        v-model="newWord"
        size="small"
        placeholder="输入新词..."
        @keyup.enter="onAdd"
      />
      <el-button size="small" type="primary" :loading="loading" :disabled="!newWord.trim()" @click="onAdd">
        添加
      </el-button>
    </div>

    <div v-if="vocabList.length === 0" class="text-center py-6 text-app-muted text-sm">
      暂无自定义词汇
    </div>

    <div v-else class="flex flex-wrap gap-2">
      <el-tag
        v-for="word in vocabList" :key="word"
        closable
        disable-transitions
        @close="onRemove(word)"
      >
        {{ word }}
      </el-tag>
    </div>
  </el-dialog>
</template>
