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
  newPromptName: string
  newPromptContent: string
  editingProfessionId: string
}>()

const emit = defineEmits<{
  'update:autoStart': [val: boolean]
  'update:tortoiseSvnPath': [val: string]
  'update:newPromptName': [val: string]
  'update:newPromptContent': [val: string]
  saveConfig: []
  testModel: [modelName: string]
  onProfessionChange: [profId: string]
  addPrompt: [profId: string]
  deletePrompt: [profId: string, promptId: string]
  savePrompt: [profId: string]
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
            <p class="text-xs text-zinc-400 mt-1">配置后 SVN 更新将使用 TortoiseSVN 界面，留空则使用命令行 svn</p>
          </div>
        </div>
      </el-tab-pane>

      <!-- AI 模型配置 -->
      <el-tab-pane label="AI 模型配置">
        <div class="py-4 space-y-4 max-h-[400px] overflow-y-auto pr-2">
          <div v-for="model in models" :key="model.name" class="p-4 bg-zinc-50 border border-zinc-100 rounded-lg">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold">{{ model.name }}</span>
              <el-tag size="small" :type="model.type === 'local' ? 'info' : 'primary'">
                {{ model.type === 'local' ? '本地' : '云端' }}
              </el-tag>
            </div>
            <div v-if="modelConfigs[model.name]" class="space-y-3">
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-zinc-500 block mb-1">模型 ID</label>
                <el-input
                  v-model="modelConfigs[model.name].modelId" size="small"
                  placeholder="例如：deepseek-chat"
                />
              </div>
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-zinc-500 block mb-1">API Key</label>
                <el-input
                  v-model="modelConfigs[model.name].apiKey"
                  type="password" show-password size="small" placeholder="sk-..."
                />
              </div>
              <div v-if="model.type === 'local'">
                <label class="text-xs text-zinc-500 block mb-1">本地地址</label>
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
            <label class="text-sm font-semibold text-zinc-700 block mb-2">选择职业</label>
            <el-select
              :model-value="selectedImitationProfession" size="default" class="w-full"
              @change="(val: string) => emit('onProfessionChange', val)"
            >
              <el-option v-for="p in professionsFull" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </div>
          <template v-if="selectedImitationProfession">
            <h3 class="text-sm font-semibold text-zinc-700 mb-3">
              {{ professionsFull.find(p => p.id === selectedImitationProfession)?.name }} - 仿写Prompt列表
            </h3>
            <div class="space-y-3 max-h-[240px] overflow-y-auto mb-4">
              <div
                v-for="prompt in (professionsFull.find(p => p.id === selectedImitationProfession)?.prompts || [])"
                :key="prompt.id"
                class="border border-zinc-200 rounded-lg p-3 bg-white"
              >
                <div class="flex items-center justify-between mb-2">
                  <input
                    class="text-sm font-medium border-0 bg-transparent focus:outline-none focus:ring-0 w-40"
                    v-model="prompt.name" placeholder="Prompt名称"
                  />
                  <el-button
                    link size="small" type="danger"
                    @click="emit('deletePrompt', editingProfessionId, prompt.id)"
                  >
                    删除
                  </el-button>
                </div>
                <textarea
                  class="text-xs text-zinc-600 w-full border border-zinc-200 rounded p-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
                  :rows="3" v-model="prompt.content"
                />
              </div>
            </div>
            <div class="border border-zinc-200 rounded-lg p-3 bg-zinc-50 mb-4">
              <div class="space-y-2">
                <div>
                  <label class="text-xs text-zinc-500 block mb-1">Prompt 名称</label>
                  <el-input
                    :model-value="newPromptName" size="small" placeholder="例如：详细策划案风格"
                    @update:model-value="(v: string) => emit('update:newPromptName', v)"
                  />
                </div>
                <div>
                  <label class="text-xs text-zinc-500 block mb-1">Prompt 内容</label>
                  <el-input
                    :model-value="newPromptContent" type="textarea" :rows="2" size="small"
                    placeholder="自定义仿写指令..."
                    @update:model-value="(v: string) => emit('update:newPromptContent', v)"
                  />
                </div>
                <div class="flex justify-end">
                  <el-button size="small" type="primary" @click="emit('addPrompt', editingProfessionId)">添加Prompt</el-button>
                </div>
              </div>
            </div>
            <el-button type="primary" size="small" @click="emit('savePrompt', editingProfessionId)">保存修改</el-button>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>
