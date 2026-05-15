<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import { Save, Trash2, ChevronLeft, ChevronRight } from 'lucide-vue-next'

const visible = defineModel<boolean>('visible', { default: false })

const props2 = defineProps<{
  libraryImageDataUri?: string
}>()

const emit2 = defineEmits<{
  saveToLibrary: [dataUri: string]
}>()

// === 生图模型列表 ===
const imageModels = [
  { name: 'GPT-Image 2', type: 'cloud' },
  { name: 'Midjourney', type: 'cloud' },
  { name: 'Google Banana', type: 'cloud' },
  { name: '豆包Seedream', type: 'cloud' },
  { name: 'Stable Diffusion（本地）', type: 'local' },
]

const selectedModel = ref('GPT-Image 2')
const rawPrompt = ref('')
const enhancedPrompt = ref('')
const isEnhancing = ref(false)
const isGenerating = ref(false)

// === 图片列表 ===
interface ImageItem {
  data_uri: string
  revised_prompt?: string
}
const images = ref<ImageItem[]>([])
const currentIndex = ref(0)
const currentImage = computed(() => images.value[currentIndex.value] || null)
const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < images.value.length - 1)

// === 修改模式 ===
const isModifyMode = ref(false)
const modifyPrompt = ref('')
const isEditing = ref(false)
const brushSize = ref(20)

// Canvas refs
const canvasRef = ref<HTMLCanvasElement | null>(null)
const editCanvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let editCtx: CanvasRenderingContext2D | null = null
let isDrawing = false
const mousePos = ref({ x: -1, y: -1 })
const canvasContainerStyle = ref({ height: '400px' })

// === 提示词增强 ===
const enhancePrompt = async () => {
  if (!rawPrompt.value.trim()) { ElMessage.warning('请输入生图提示'); return }
  isEnhancing.value = true
  try {
    const r = await axios.post(apiUrl('/api/image/enhance-prompt'), { text: rawPrompt.value.trim() })
    if (r.data.success && r.data.data?.enhanced) {
      enhancedPrompt.value = r.data.data.enhanced
    } else {
      enhancedPrompt.value = rawPrompt.value
    }
  } catch (e: any) {
    ElMessage.warning('提示增强失败: ' + getErrMsg(e))
    enhancedPrompt.value = rawPrompt.value
  } finally {
    isEnhancing.value = false
  }
}

// === 生图 ===
const generate = async () => {
  const promptText = rawPrompt.value.trim()
  if (!promptText) { ElMessage.warning('请输入生图提示'); return }
  isGenerating.value = true
  try {
    // Auto-enhance prompt first
    enhancedPrompt.value = ''
    try {
      const r = await axios.post(apiUrl('/api/image/enhance-prompt'), { text: promptText })
      if (r.data.success && r.data.data?.enhanced) {
        enhancedPrompt.value = r.data.data.enhanced
      }
    } catch { /* use raw prompt */ }
    const finalPrompt = enhancedPrompt.value || promptText
    const r = await axios.post(apiUrl('/api/image/generate'), {
      prompt: finalPrompt,
      model: selectedModel.value,
    })
    if (r.data.success && r.data.data?.data_uri) {
      images.value.push({
        data_uri: r.data.data.data_uri,
        revised_prompt: r.data.data.revised_prompt,
      })
      currentIndex.value = images.value.length - 1
      ElMessage.success('生图完成')
    } else {
      ElMessage.warning(r.data.message || '生图失败')
    }
  } catch (e: any) {
    ElMessage.error('生图失败: ' + getErrMsg(e))
  } finally {
    isGenerating.value = false
  }
}

// === 保存图片 ===
const saveImage = async () => {
  const img = currentImage.value
  if (!img) return
  const api = (window as any).electronAPI
  if (api?.saveFileAs) {
    const result = await api.saveFileAs(img.data_uri, 'image.png')
    if (result.success) ElMessage.success('已保存')
    else if (!result.error?.includes('Canceled')) ElMessage.warning('保存失败')
  } else {
    // Browser fallback: download link
    const a = document.createElement('a')
    a.href = img.data_uri
    a.download = `generated_${Date.now()}.png`
    a.click()
  }
}

// === 修改模式 ===
const enterModifyMode = async () => {
  if (!currentImage.value) return
  isModifyMode.value = true
  modifyPrompt.value = ''
  await nextTick()
  initCanvas()
}

const exitModifyMode = () => {
  isModifyMode.value = false
  modifyPrompt.value = ''
  isDrawing = false
}

// === Canvas: init and draw the image for editing ===
const initCanvas = () => {
  const canvas = canvasRef.value
  if (!canvas || !currentImage.value) return
  const img = new Image()
  img.onload = () => {
    const maxW = 700, maxH = 500
    let w = img.naturalWidth, h = img.naturalHeight
    if (w > maxW) { h = h * maxW / w; w = maxW }
    if (h > maxH) { w = w * maxH / h; h = maxH }
    w = Math.round(w); h = Math.round(h)

    canvas.width = w
    canvas.height = h
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'
    ctx = canvas.getContext('2d')
    if (ctx) ctx.drawImage(img, 0, 0, w, h)

    const overlay = editCanvasRef.value
    if (overlay) {
      overlay.width = w
      overlay.height = h
      overlay.style.width = w + 'px'
      overlay.style.height = h + 'px'
      editCtx = overlay.getContext('2d')
    }

    canvasContainerStyle.value = { height: h + 'px' }
  }
  img.src = currentImage.value.data_uri
}

// === Canvas: mouse events for drawing the mask ===
const onMouseDown = (e: MouseEvent) => {
  if (!editCtx || !editCanvasRef.value) return
  isDrawing = true
  const rect = editCanvasRef.value.getBoundingClientRect()
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  mousePos.value = {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY,
  }
  drawBrush(e)
}

const onMouseMove = (e: MouseEvent) => {
  if (!editCanvasRef.value) return
  const rect = editCanvasRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  // Scale mouse coords to canvas coords if CSS size differs from canvas size
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  mousePos.value = { x: x * scaleX, y: y * scaleY }
  if (isDrawing && editCtx) drawBrush(e)
}

const onMouseUp = () => { isDrawing = false }
const onMouseLeave = () => { isDrawing = false; mousePos.value = { x: -1, y: -1 } }

const drawBrush = (e: MouseEvent) => {
  if (!editCtx || !editCanvasRef.value) return
  const rect = editCanvasRef.value.getBoundingClientRect()
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  const x = (e.clientX - rect.left) * scaleX
  const y = (e.clientY - rect.top) * scaleY

  editCtx.globalCompositeOperation = 'source-over'
  editCtx.fillStyle = 'rgba(255, 0, 0, 0.4)'
  editCtx.beginPath()
  editCtx.arc(x, y, brushSize.value, 0, Math.PI * 2)
  editCtx.fill()
}

// Watch for library edit: load image and enter modify mode
watch(() => props2.libraryImageDataUri, (uri) => {
  if (uri && visible.value) {
    images.value = [{ data_uri: uri, revised_prompt: '' }]
    currentIndex.value = 0
    nextTick(() => enterModifyMode())
  }
})
watch(visible, (v) => {
  if (!v) {
    isModifyMode.value = false
    enhancedPrompt.value = ''
  }
})

const clearMask = () => {
  if (!editCtx || !editCanvasRef.value) return
  editCtx.clearRect(0, 0, editCanvasRef.value.width, editCanvasRef.value.height)
}

// Generate mask in the correct format for the edit API:
// opaque white = keep, transparent = modify (inverse of display canvas)
const generateMaskDataUrl = (): string => {
  const src = editCanvasRef.value
  if (!src) return ''
  const w = src.width, h = src.height
  const mc = document.createElement('canvas')
  mc.width = w; mc.height = h
  const mtx = mc.getContext('2d')!
  // Fill with opaque white (keep everything by default)
  mtx.fillStyle = '#ffffff'
  mtx.fillRect(0, 0, w, h)
  // Get painted pixels from the display canvas (where alpha > 0 = user painted)
  const srcCtx = src.getContext('2d')!
  const srcData = srcCtx.getImageData(0, 0, w, h)
  const dstData = mtx.getImageData(0, 0, w, h)
  // Wherever the user painted (alpha > 10), set mask to transparent (= modify)
  for (let i = 3; i < srcData.data.length; i += 4) {
    if (srcData.data[i] > 10) {
      dstData.data[i] = 0 // alpha = 0 → transparent → modify this area
    }
  }
  mtx.putImageData(dstData, 0, 0)
  return mc.toDataURL('image/png')
}

// === 提交修改 ===
const submitEdit = async () => {
  if (!modifyPrompt.value.trim()) { ElMessage.warning('请输入修改需求'); return }
  if (!currentImage.value) return
  isEditing.value = true
  try {
    // Get mask data URL (correct format: opaque white bg, transparent = edit area)
    let maskUri = ''
    if (editCanvasRef.value) {
      maskUri = generateMaskDataUrl()
    }
    const r = await axios.post(apiUrl('/api/image/edit'), {
      model: selectedModel.value,
      prompt: modifyPrompt.value.trim(),
      data_uri: currentImage.value.data_uri,
      mask_uri: maskUri,
    })
    if (r.data.success && r.data.data?.data_uri) {
      images.value.push({
        data_uri: r.data.data.data_uri,
        revised_prompt: modifyPrompt.value,
      })
      currentIndex.value = images.value.length - 1
      exitModifyMode()
      ElMessage.success('修改完成')
    } else {
      ElMessage.warning(r.data.message || '修改失败')
    }
  } catch (e: any) {
    ElMessage.error('修改失败: ' + getErrMsg(e))
  } finally {
    isEditing.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="图片工具"
    width="820px"
    top="3vh"
    class="image-tool-dialog"
  >
    <div class="space-y-4">
      <!-- Model selector + prompt -->
      <div class="flex gap-2 items-start">
        <el-select v-model="selectedModel" size="small" class="!w-44" placeholder="选择生图模型">
          <el-option
            v-for="m in imageModels"
            :key="m.name"
            :label="m.name"
            :value="m.name"
          >
            <span>{{ m.name }}</span>
            <el-tag v-if="m.type === 'local'" size="small" type="info" class="ml-2">本地</el-tag>
            <el-tag v-else size="small" type="primary" class="ml-2">云端</el-tag>
          </el-option>
        </el-select>
        <div class="flex-1 flex flex-col gap-2">
          <el-input
            v-model="rawPrompt"
            type="textarea" :rows="3"
            size="small"
            placeholder="输入自然语言描述，AI将自动优化为专业prompt..."
            @keyup.ctrl.enter="generate"
          />
          <div class="flex justify-end">
            <el-button size="small" type="primary" :loading="isGenerating" @click="generate">生图</el-button>
          </div>
        </div>
      </div>

      <!-- Main content: image area or modify mode -->
      <div v-if="!isModifyMode" class="flex flex-col items-center gap-3 min-h-[300px]">
        <!-- Generated images area -->
        <div v-if="images.length > 0" class="relative w-full flex items-center justify-center gap-2">
          <el-button :disabled="!hasPrev" circle size="small" @click="currentIndex--">
            <ChevronLeft class="w-4 h-4" />
          </el-button>
          <div class="flex-1 flex justify-center">
            <img
              :src="currentImage?.data_uri"
              class="max-w-full max-h-[400px] rounded-lg shadow-md object-contain"
              alt="生成的图片"
            />
          </div>
          <el-button :disabled="!hasNext" circle size="small" @click="currentIndex++">
            <ChevronRight class="w-4 h-4" />
          </el-button>
        </div>

        <!-- Empty state -->
        <div v-else class="text-app-muted text-sm py-12">
          输入提示词后点击"生图"开始生成
        </div>

        <!-- Action buttons -->
        <div v-if="images.length > 0" class="flex gap-2">
          <el-button size="small" @click="saveImage">
            <Save class="w-3.5 h-3.5 mr-1" />导出
          </el-button>
          <el-button size="small" type="success" @click="emit2('saveToLibrary', currentImage?.data_uri || '')">
            <Save class="w-3.5 h-3.5 mr-1" />保存到图片库
          </el-button>
          <el-button size="small" type="primary" @click="enterModifyMode">
            修改
          </el-button>
          <el-button size="small" type="danger" @click="images = []; currentIndex = 0">
            <Trash2 class="w-3.5 h-3.5 mr-1" />清空
          </el-button>
        </div>

        <!-- Page indicator -->
        <div v-if="images.length > 1" class="text-xs text-app-muted">
          {{ currentIndex + 1 }} / {{ images.length }}
        </div>
      </div>

      <!-- Modify mode: canvas with brush -->
      <div v-else class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium">在图片上涂抹要修改的区域</span>
          <div class="flex items-center gap-2">
            <span class="text-xs text-app-muted">画笔大小:</span>
            <el-slider v-model="brushSize" :min="5" :max="80" class="!w-24" />
            <span class="text-xs text-app-muted w-8">{{ brushSize }}px</span>
          </div>
        </div>

        <!-- Canvas stack -->
        <div class="relative border rounded-lg overflow-hidden" :style="canvasContainerStyle">
          <canvas
            ref="canvasRef"
            class="absolute inset-0"
          />
          <canvas
            ref="editCanvasRef"
            class="absolute inset-0 cursor-crosshair"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
            @mouseleave="onMouseLeave"
          />
          <!-- Brush cursor preview circle -->
          <div
            v-if="mousePos.x >= 0"
            class="absolute pointer-events-none rounded-full border-2 border-white"
            :style="{
              width: brushSize * 2 + 'px',
              height: brushSize * 2 + 'px',
              left: mousePos.x - brushSize + 'px',
              top: mousePos.y - brushSize + 'px',
            }"
          />
        </div>

        <div class="flex gap-2">
          <el-button size="small" @click="clearMask">清除涂抹</el-button>
          <el-input
            v-model="modifyPrompt"
            size="small"
            placeholder="输入修改需求（如：把背景换成森林）"
            class="flex-1"
            @keyup.enter="submitEdit"
          />
          <el-button size="small" type="primary" :loading="isEditing" @click="submitEdit">确认修改</el-button>
          <el-button size="small" @click="exitModifyMode">返回</el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.image-tool-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}
</style>
