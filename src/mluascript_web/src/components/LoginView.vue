<script setup>
import { ref } from 'vue'
import { NButton, NCard, NForm, NFormItem, NInput, NText } from 'naive-ui'
import { actions } from '../store'

const username = ref('admin')
const password = ref('')
const loading = ref(false)
const errorText = ref('')

async function submitLogin() {
  if (loading.value) return
  loading.value = true
  errorText.value = ''
  try {
    await actions.login(username.value.trim(), password.value)
  } catch (error) {
    errorText.value = error?.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-shell">
    <n-card class="login-panel" :bordered="false">
      <div class="login-brand">
        <img src="/favicon.ico" alt="MluaScript" class="login-logo" />
        <h1>MluaScript</h1>
      </div>

      <n-form @submit.prevent="submitLogin">
        <n-form-item label="用户名">
          <n-input v-model:value="username" placeholder="请输入用户名" autocomplete="username" @keydown.enter.prevent="submitLogin" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input
            v-model:value="password"
            type="password"
            placeholder="请输入密码"
            show-password-on="click"
            autocomplete="current-password"
            @keydown.enter.prevent="submitLogin"
          />
        </n-form-item>
        <n-text v-if="errorText" type="error" class="login-error">{{ errorText }}</n-text>
        <n-button type="primary" block :loading="loading" @click="submitLogin">登录</n-button>
      </n-form>
    </n-card>
  </main>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(26, 94, 128, 0.18), transparent 42%),
    var(--color-background);
}

.login-panel {
  width: min(100%, 360px);
  border-radius: 8px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.login-logo {
  width: 36px;
  height: 36px;
}

.login-brand h1 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}

.login-error {
  display: block;
  margin: -4px 0 14px;
}
</style>
