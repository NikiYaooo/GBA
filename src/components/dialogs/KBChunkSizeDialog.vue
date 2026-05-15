<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  chunkSizeMin: number
  chunkSizeMax: number
  loading: boolean
}>()

const emit = defineEmits<{
  save: [chunkSizeMin: number, chunkSizeMax: number]
  rechunk: []
}>()

const minVal = ref(100)
const maxVal = ref(500)

watch(() => visible.value, (v) => {
  if (v) {
    minVal.value = props.chunkSizeMin
    maxVal.value = props.chunkSizeMax
  }
})

const onSave = () => {
  if (minVal.value >= maxVal.value) {
    ElMessage.warning('最小切片大小不能大于等于最大切片大小')
    return
  }
  emit('save', minVal.value, maxVal.value)
  visible.value = false
}

const onRechunk = () => {
  emit('rechunk')
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="切片设置" width="480px" top="25vh">
    <div class="space-y-6 px-2">
      <div>
        <label class="text-sm font-medium text-app block mb-2">
          最小切片大小: {{ minVal }}
        </label>
        <el-slider v-model="minVal" :min="50" :max="500" :step="10" show-input />
      </div>
      <div>
        <label class="text-sm font-medium text-app block mb-2">
          最大切片大小: {{ maxVal }}
        </label>
        <el-slider v-model="maxVal" :min="100" :max="2000" :step="10" show-input />
      </div>
      <div v-if="minVal >= maxVal" class="text-xs text-red-500">
        最小切片大小必须小于最大切片大小
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :loading="loading" @click="onRechunk">保存并重新切片</el-button>
      <el-button type="primary" :loading="loading" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>
