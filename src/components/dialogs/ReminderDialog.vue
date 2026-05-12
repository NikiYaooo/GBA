<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  editReminder: any | null
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  save: [data: { content: string; month: number | null; day: number | null; hour: number; minute: number }]
}>()

const content = ref('')
const month = ref<number | null>(null)
const day = ref<number | null>(null)
const hour = ref(9)
const minute = ref(0)

const monthOptions = Array.from({ length: 12 }, (_, i) => ({ label: `${i + 1}月`, value: i + 1 }))
const dayOptions = Array.from({ length: 31 }, (_, i) => ({ label: `${i + 1}日`, value: i + 1 }))
const hourOptions = Array.from({ length: 24 }, (_, i) => ({ label: `${String(i).padStart(2, '0')}时`, value: i }))
const minuteOptions = Array.from({ length: 60 }, (_, i) => ({ label: `${String(i).padStart(2, '0')}分`, value: i }))

const resetForm = () => {
  content.value = ''
  month.value = null
  day.value = null
  hour.value = 9
  minute.value = 0
}

watch(() => props.visible, (v) => {
  if (v) {
    if (props.editReminder) {
      content.value = props.editReminder.content
      month.value = props.editReminder.month
      day.value = props.editReminder.day
      hour.value = props.editReminder.hour
      minute.value = props.editReminder.minute
    } else {
      resetForm()
    }
  }
})

const submit = () => {
  if (!content.value.trim()) return
  emit('save', {
    content: content.value.trim(),
    month: month.value,
    day: day.value,
    hour: hour.value,
    minute: minute.value,
  })
  emit('update:visible', false)
}
</script>

<template>
  <el-dialog :model-value="visible" title="计划提醒" width="420px" top="20vh"
    @update:model-value="(v: boolean) => emit('update:visible', v)">
    <div class="space-y-4">
      <div>
        <label class="text-sm font-medium block mb-1">提醒内容</label>
        <el-input v-model="content" type="textarea" :rows="3" placeholder="输入提醒内容..." />
      </div>
      <div>
        <label class="text-sm font-medium block mb-1">提醒时间</label>
        <div class="flex items-center gap-2">
          <el-select v-model="month" placeholder="每月" clearable class="w-24" size="small">
            <el-option v-for="o in monthOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-select v-model="day" placeholder="每日" clearable class="w-24" size="small">
            <el-option v-for="o in dayOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-select v-model="hour" class="w-24" size="small">
            <el-option v-for="o in hourOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <el-select v-model="minute" class="w-24" size="small">
            <el-option v-for="o in minuteOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </div>
        <p class="text-xs text-app-muted mt-1">
          {{ month ? `${month}月` : '每月' }} {{ day ? `${day}日` : '每日' }} {{ String(hour).padStart(2, '0') }}:{{ String(minute).padStart(2, '0') }}
        </p>
      </div>
    </div>
    <template #footer>
      <el-button size="small" @click="emit('update:visible', false)">取消</el-button>
      <el-button size="small" type="primary" @click="submit" :disabled="!content.trim()">确定</el-button>
    </template>
  </el-dialog>
</template>
