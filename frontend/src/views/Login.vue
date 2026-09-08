<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'
import type { LoginRequest } from '../types/auth'
import { getApiErrorMessage } from '../utils/api-error'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMessage = ref('')
const form = reactive<LoginRequest>({
  username: '',
  password: '',
})
const rules: FormRules<LoginRequest> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function readableError(error: unknown): string {
  return getApiErrorMessage(error, '登录失败，请检查用户名和密码。')
}

function loginRedirect(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/dashboard'
}

async function submitLogin(): Promise<void> {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    await userStore.login(form.username, form.password)
    await router.replace(loginRedirect(route.query.redirect))
  } catch (error: unknown) {
    errorMessage.value = readableError(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <el-card class="login-card" shadow="never">
      <template #header>
        <div>
          <h1>短剧数据管理与分析系统</h1>
          <p>请使用系统账号登录</p>
        </div>
      </template>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" :disabled="loading" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
            :disabled="loading"
            @keyup.enter="submitLogin"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" @click="submitLogin">
          登录
        </el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--el-bg-color-page);
}

.login-card {
  width: min(420px, 100%);
}

h1 {
  margin: 0;
  font-size: 22px;
}

p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
}

.el-alert {
  margin-bottom: 18px;
}

.el-button {
  width: 100%;
}
</style>
