<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getDrama } from '../../api/drama'
import type { Drama } from '../../types/drama'
import { getApiErrorMessage } from '../../utils/api-error'

const route = useRoute()
const loading = ref(false)
const errorMessage = ref('')
const drama = ref<Drama | null>(null)

async function loadDrama(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    drama.value = await getDrama(Number(route.params.id))
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '短剧详情加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadDrama())
</script>

<template>
  <main class="detail-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Drama Detail</p>
        <h1>{{ drama?.drama_name ?? '短剧详情' }}</h1>
      </div>
      <div class="header-actions">
        <router-link to="/dramas"><el-button>返回短剧管理</el-button></router-link>
        <router-link v-if="drama" :to="{ path: '/analytics', query: { drama_id: drama.drama_id } }">
          <el-button type="primary">查看分析</el-button>
        </router-link>
      </div>
    </header>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-card v-loading="loading" shadow="never">
      <el-descriptions v-if="drama" :column="2" border>
        <el-descriptions-item label="业务编码">{{ drama.drama_code }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ drama.status }}</el-descriptions-item>
        <el-descriptions-item label="标签" :span="2">
          <div class="tag-list">
            <el-tag v-for="tag in drama.tags" :key="tag.tag_id" effect="plain">{{ tag.tag_name }}</el-tag>
            <span v-if="drama.tags.length === 0" class="muted">暂无标签</span>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="平台" :span="2">
          <div class="tag-list">
            <el-tag v-for="platform in drama.platforms" :key="platform.platform_id" type="info">
              {{ platform.platform_name }}
            </el-tag>
            <span v-if="drama.platforms.length === 0" class="muted">暂无平台</span>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="简介" :span="2">{{ drama.synopsis || '暂无简介' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </main>
</template>

<style scoped>
.detail-page { min-height: 100vh; padding: 28px; background: var(--el-bg-color-page); color: var(--el-text-color-primary); }
.page-header { display: flex; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 32px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.header-actions, .tag-list { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.muted { color: var(--el-text-color-secondary); }
@media (max-width: 720px) { .detail-page { padding: 18px; } .page-header { flex-direction: column; } }
</style>
