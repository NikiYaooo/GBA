<script setup lang="ts">
import type { ModelConfig, Profession, PromptTemplate } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

defineProps<{
  autoStart: boolean
  tortoiseSvnPath: string
  models: { name: string; type: 'cloud' | 'local' }[]
  modelConfigs: Record<string, ModelConfig>
  testingModel: string
  professionsFull: Profession[]
  selectedImitationProfession: string
  editingProfessionId: string
  isDark: boolean
}>()

const emit = defineEmits<{
  'update:autoStart': [val: boolean]
  'update:tortoiseSvnPath': [val: string]
  saveConfig: []
  testModel: [modelName: string]
  onProfessionChange: [profId: string]
  'update:isDark': [val: boolean]
}>()
</script>

<template>
  <el-dialog v-model="visible" title="软件设置" width="600px" top="5vh">
    <el-tabs>
      <!-- 通用设置 -->
      <el-tab-pane label="通用设置">
        <div class="py-4 space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">开机自动启动</span>
            <el-switch
              :model-value="autoStart"
              @change="(val: boolean) => emit('update:autoStart', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm font-medium">夜间模式</span>
              <p class="text-xs text-app-muted mt-0.5">切换深色/浅色主题</p>
            </div>
            <el-switch
              :model-value="isDark"
              @change="(val: boolean) => emit('update:isDark', val)"
            />
          </div>
          <div>
            <label class="text-sm font-medium block mb-2">TortoiseSVN 路径</label>
            <div class="flex gap-2">
              <el-input
                :model-value="tortoiseSvnPath" size="small"
                placeholder="例如：C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe"
                @update:model-value="(v: string) => emit('update:tortoiseSvnPath', v)"
              />
              <el-button size="small" @click="emit('saveConfig')">保存</el-button>
            </div>
            <p class="text-xs text-app-muted mt-1">配置后 SVN 更新将使用 TortoiseSVN 界面，留空则使用命令行 svn</p>
          </div>
        </div>
      </el-tab-pane>

      <!-- AI 模型配置 -->
      <el-tab-pane label="AI 模型配置">
        <div class="py-4 space-y-4 max-h-[400px] overflow-y-auto pr-2">
          <div v-for="model in models" :key="model.name" class="p-4 bg-primary-light border border-app-light rounded-lg">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold">{{ model.name }}</span>
              <el-tag size="small" :type="model.type === 'local' ? 'info' : 'primary'">
                {{ model.type === 'local' ? '本地' : '云端' }}
              </el-tag>
            </div>
            <div v-if="modelConfigs[model.name]" class="space-y-3">
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-app-secondary block mb-1">模型 ID</label>
                <el-input
                  v-model="modelConfigs[model.name].modelId" size="small"
                  placeholder="例如：deepseek-chat"
                />
              </div>
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-app-secondary block mb-1">API Key</label>
                <el-input
                  v-model="modelConfigs[model.name].apiKey"
                  type="password" show-password size="small" placeholder="sk-..."
                />
              </div>
              <div v-if="model.type === 'local'">
                <label class="text-xs text-app-secondary block mb-1">本地地址</label>
                <el-input
                  v-model="modelConfigs[model.name].modelId" size="small"
                  placeholder="http://localhost:11434"
                />
              </div>
              <el-button
                v-if="modelConfigs[model.name].apiKey || modelConfigs[model.name].modelId"
                size="small" :loading="testingModel === model.name"
                @click="emit('testModel', model.name)"
              >
                连接测试
              </el-button>
            </div>
          </div>
        </div>
        <div class="mt-4 flex justify-end">
          <el-button type="primary" @click="emit('saveConfig')">保存模型配置</el-button>
        </div>
      </el-tab-pane>

      <!-- 职业角色 -->
      <el-tab-pane label="职业角色">
        <div class="py-4 pr-2">
          <div class="mb-6">
            <label class="text-sm font-semibold text-app block mb-2">选择职业</label>
            <el-select
              :model-value="selectedImitationProfession" size="default" class="w-full"
              @change="(val: string) => emit('onProfessionChange', val)"
            >
              <el-option v-for="p in professionsFull" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </div>
          <template v-if="selectedImitationProfession">
            <h3 class="text-sm font-semibold text-app mb-3">
              {{ professionsFull.find(p => p.id === selectedImitationProfession)?.name }} - 内置仿写指令
            </h3>
            <p class="text-xs text-app-muted mb-3">仿写 Prompt 已内置在代码中，不可编辑。选择职业后可查看对应 Prompt。</p>
            <div class="space-y-3 max-h-[300px] overflow-y-auto">
              <div
                v-for="prompt in (professionsFull.find(p => p.id === selectedImitationProfession)?.prompts || [])"
                :key="prompt.id"
                class="border border-app rounded-lg p-3 bg-surface"
              >
                <div class="text-sm font-medium mb-2">{{ prompt.name }}</div>
                <div class="text-xs text-app-secondary whitespace-pre-wrap leading-relaxed">{{ prompt.content }}</div>
              </div>
            </div>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>
