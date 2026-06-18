<template>
  <div class="page">
    <div class="page-toolbar">
      <h3 class="mono" style="font-size:15px;font-weight:600">账号管理</h3>
      <el-button type="primary" @click="handleOpenCreate()">+ 添加账号</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="data" v-loading="loading">
        <el-table-column prop="platform" label="平台" width="120">
          <template #default="{ row }"><el-tag size="small">{{ platformLabel(row.platform) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="login_type" label="登录方式" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.login_type === 'api' ? 'success' : 'warning'" effect="dark">
              {{ row.login_type === 'api' ? 'API' : 'Cookie' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="account_name" label="账号名称" min-width="140" />
        <el-table-column prop="session_state_path" label="会话状态" width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleOpenEdit(row)">编辑</el-button>
            <el-button text size="small" @click="check(row)">检测</el-button>
            <el-button text type="danger" size="small" @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" destroy-on-close>
      <el-form :model="form" label-width="100px" label-position="left">
        <el-form-item label="平台" required>
          <el-select v-model="form.platform" style="width:100%">
            <el-option v-for="p in platforms" :key="p.key" :label="p.label" :value="p.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="登录方式" required>
          <el-select v-model="form.login_type" style="width:100%">
            <el-option label="Cookie / 浏览器会话" value="cookie" />
            <el-option label="API Token" value="api" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号名称">
          <el-input v-model="form.account_name" />
        </el-form-item>

        <!-- Cookie 粘贴区 -->
        <el-form-item label="粘贴 Cookie" v-if="form.login_type === 'cookie'">
          <div style="width:100%">
            <el-input
              v-model="cookieInput"
              type="textarea"
              :rows="4"
              placeholder="粘贴浏览器 Cookie 字符串&#10;支持格式：name=value; name2=value2 或 Netscape cookie.txt 格式"
            />
            <div style="margin-top:6px;display:flex;gap:8px;align-items:center">
              <el-button
                size="small"
                type="primary"
                :loading="cookieLoading"
                :disabled="!cookieInput.trim()"
                @click="importCookie"
              >解析并导入</el-button>
              <span v-if="cookieResult" style="font-size:12px;color:var(--el-color-success)">{{ cookieResult }}</span>
            </div>
            <div style="margin-top:4px;font-size:11px;color:var(--el-text-color-placeholder)">
              导入后 Cookie 将保存为浏览器会话文件，账号状态自动设为 active
            </div>
          </div>
        </el-form-item>

        <!-- 各平台 Cookie 获取指南（Cookie 模式 + 已选平台时显示） -->
        <el-form-item v-if="form.login_type === 'cookie' && form.platform" style="margin-bottom:8px">
          <el-collapse style="width:100%">
            <el-collapse-item>
              <template #title>
                <span style="font-size:13px;font-weight:600;color:var(--el-color-primary)">
                  📖 {{ platformLabel(form.platform) }} Cookie 获取指南
                </span>
              </template>

              <!-- 小红书 -->
              <div v-if="form.platform === 'xiaohongshu'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://creator.xiaohongshu.com" target="_blank">creator.xiaohongshu.com</a> 并扫码登录</div>
                <div class="guide-step"><b>2.</b> 按 <kbd>F12</kbd> 打开开发者工具 → 切换至 <b>Application</b>（应用程序）标签</div>
                <div class="guide-step"><b>3.</b> 左侧 Storage → <b>Cookies</b> → 点击 <code>creator.xiaohongshu.com</code></div>
                <div class="guide-step"><b>4.</b> 在 Console 中粘贴以下脚本，回车后自动复制：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.xiaohongshu }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('xiaohongshu')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>a1</code>、<code>webId</code>、<code>web_session</code>、<code>acw_tc</code>。过期后需重新获取。</div>
              </div>

              <!-- 知乎 -->
              <div v-if="form.platform === 'zhihu'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://www.zhihu.com" target="_blank">zhihu.com</a> 并登录</div>
                <div class="guide-step"><b>2.</b> <kbd>F12</kbd> → <b>Application</b> → Cookies → <code>zhihu.com</code></div>
                <div class="guide-step"><b>3.</b> Console 中执行脚本自动导出：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.zhihu }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('zhihu')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>z_c0</code>（登录令牌）、<code>d_c0</code>、<code>_xsrf</code>。</div>
              </div>

              <!-- 微博 -->
              <div v-if="form.platform === 'weibo'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://weibo.com" target="_blank">weibo.com</a> 并登录</div>
                <div class="guide-step"><b>2.</b> <kbd>F12</kbd> → <b>Application</b> → Cookies → <code>weibo.com</code></div>
                <div class="guide-step"><b>3.</b> Console 中执行脚本自动导出：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.weibo }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('weibo')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>SUB</code>、<code>SUBP</code>、<code>login_sid_t</code>。微博 Cookie 有效期较长但仍建议定期更新。</div>
              </div>

              <!-- 微信公众号 -->
              <div v-if="form.platform === 'wechat'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://mp.weixin.qq.com" target="_blank">mp.weixin.qq.com</a> 并扫码登录</div>
                <div class="guide-step"><b>2.</b> <kbd>F12</kbd> → <b>Application</b> → Cookies → <code>mp.weixin.qq.com</code></div>
                <div class="guide-step"><b>3.</b> Console 中执行脚本自动导出：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.wechat }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('wechat')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>token</code>、<code>cookie</code>（公众号后台使用）。<br>⚠️ 微信公众号后台 Cookie 有效期通常为 2 小时，过期后需重新扫码。</div>
              </div>

              <!-- 今日头条 -->
              <div v-if="form.platform === 'toutiao'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://mp.toutiao.com" target="_blank">mp.toutiao.com</a> 并登录</div>
                <div class="guide-step"><b>2.</b> <kbd>F12</kbd> → <b>Application</b> → Cookies → <code>mp.toutiao.com</code></div>
                <div class="guide-step"><b>3.</b> Console 中执行脚本自动导出：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.toutiao }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('toutiao')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>sessionid</code>、<code>sso_uid_tt</code>。头条创作者后台 Cookie 可能会跨域，建议在 <code>mp.toutiao.com</code> 下获取。</div>
              </div>

              <!-- 抖音图文 -->
              <div v-if="form.platform === 'douyin'" class="cookie-guide">
                <div class="guide-step"><b>1.</b> 打开 <a href="https://creator.douyin.com" target="_blank">creator.douyin.com</a> 并扫码登录</div>
                <div class="guide-step"><b>2.</b> <kbd>F12</kbd> → <b>Application</b> → Cookies → <code>creator.douyin.com</code></div>
                <div class="guide-step"><b>3.</b> Console 中执行脚本自动导出：</div>
                <div class="guide-script">
                  <code>{{ cookieScripts.douyin }}</code>
                  <el-button size="small" text type="primary" @click="copyScript('douyin')">复制脚本</el-button>
                </div>
                <div class="guide-note">⚠️ 核心 Cookie：<code>sessionid</code>、<code>passport_csrf_token</code>。<br>⚠️ 抖音创作者平台 Cookie 有效期短，建议操作前重新获取。</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>

        <!-- API Token 区 -->
        <el-form-item label="Auth JSON" v-if="form.login_type === 'api'">
          <el-input v-model="form.auth_config" type="textarea" :rows="5" placeholder='{"appid": "...", "appsecret": "..."}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAccounts, createAccount, updateAccount, deleteAccount,
  checkSession, importAccountCookie
} from '@/api/accounts'
import { useCrud } from '@/composables/useCrud'

const crud = useCrud(getAccounts, createAccount, updateAccount, deleteAccount)
const { data, loading, dialogVisible, dialogTitle, form, formLoading, isEdit, editId,
        openCreate, openEdit, remove } = crud

// ── Cookie 粘贴导入状态 ──
const cookieInput = ref('')
const cookieLoading = ref(false)
const cookieResult = ref('')

// ── 各平台 Cookie 获取 Console 脚本 ──
const cookieScripts = {
  xiaohongshu: `// 在小红书创作者平台页面 Console 中执行，自动复制 Cookie
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
  zhihu: `// 在知乎页面 Console 中执行，自动复制 Cookie
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
  weibo: `// 在微博页面 Console 中执行，自动复制 Cookie
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
  wechat: `// 在微信公众号后台 (mp.weixin.qq.com) Console 中执行
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
  toutiao: `// 在头条创作者后台 (mp.toutiao.com) Console 中执行
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
  douyin: `// 在抖音创作者平台 (creator.douyin.com) Console 中执行
copy(document.cookie);
console.log('Cookie 已复制，粘贴到输入框即可');`,
}

function copyScript(platform) {
  navigator.clipboard.writeText(cookieScripts[platform]).then(() => {
    ElMessage.success('脚本已复制，请在对应平台 Console 中粘贴执行')
  }).catch(() => {
    ElMessage.warning('复制失败，请手动选中脚本复制')
  })
}

async function importCookie() {
  if (!cookieInput.value.trim()) return
  cookieLoading.value = true
  cookieResult.value = ''
  try {
    const targetId = editId.value || form.value.id
    if (!targetId) {
      ElMessage.warning('请先保存账号后再导入 Cookie')
      cookieLoading.value = false
      return
    }
    const res = await importAccountCookie(targetId, cookieInput.value, form.value.platform)
    cookieResult.value = `已导入 ${res.data?.cookie_count || res?.cookie_count || '?'} 条 Cookie`
    ElMessage.success('Cookie 导入成功，账号状态已设为 active')
    cookieInput.value = ''
    crud.fetch()
  } catch (e) {
    // error handled by interceptor
  } finally {
    cookieLoading.value = false
  }
}

// ── 自定义 Submit：Cookie 类型创建后自动进入编辑模式 ──
async function handleSubmit() {
  formLoading.value = true
  try {
    if (isEdit.value) {
      await updateAccount(editId.value, form.value)
      ElMessage.success('更新成功')
      dialogVisible.value = false
    } else {
      const res = await createAccount(form.value)
      const newId = res.id || res.data?.id
      ElMessage.success('创建成功')
      // Cookie 类型：不关闭弹窗，自动切换到编辑模式展示粘贴区
      if (form.value.login_type === 'cookie' && newId) {
        editId.value = newId
        isEdit.value = true
        dialogTitle.value = '粘贴 Cookie — ' + (form.value.account_name || form.value.platform)
        formLoading.value = false
        crud.fetch()
        return
      }
      dialogVisible.value = false
    }
    crud.fetch()
  } finally {
    formLoading.value = false
  }
}

// 重置 cookie 状态
function handleOpenCreate() {
  openCreate()
  cookieInput.value = ''
  cookieResult.value = ''
}

function handleOpenEdit(row) {
  openEdit(row)
  cookieInput.value = ''
  cookieResult.value = ''
}

const platforms = [
  { key: 'xiaohongshu', label: '小红书' },
  { key: 'zhihu', label: '知乎' },
  { key: 'weibo', label: '微博' },
  { key: 'wechat', label: '微信公众号' },
  { key: 'toutiao', label: '今日头条' },
  { key: 'douyin', label: '抖音图文' }
]
const platformMap = Object.fromEntries(platforms.map(p => [p.key, p.label]))
function platformLabel(k) { return platformMap[k] || k }

async function check(row) {
  try {
    await checkSession(row.id)
    ElMessage.success('会话正常')
  } catch { /* error handled by interceptor */ }
}

onMounted(() => crud.fetch())
</script>

<style lang="scss" scoped>
.page { animation: fadeIn 0.3s ease; }
.page-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

/* ── Cookie 获取指南样式 ── */
.cookie-guide {
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
  padding: 4px 0;
}
.guide-step {
  margin-bottom: 10px;
}
.guide-step a {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.guide-step kbd {
  display: inline-block;
  padding: 1px 6px;
  font-size: 12px;
  font-family: inherit;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 3px;
  box-shadow: 0 1px 0 var(--el-border-color);
}
.guide-step code {
  padding: 1px 5px;
  font-size: 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 3px;
  color: var(--el-color-primary);
}
.guide-script {
  margin: 10px 0;
  padding: 12px;
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.guide-script code {
  flex: 1;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--el-text-color-secondary);
  padding: 4px 0;
  background: transparent;
}
.guide-note {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--el-color-warning-light-9);
  border-left: 3px solid var(--el-color-warning);
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}
.guide-note code {
  padding: 1px 5px;
  font-size: 11px;
  background: var(--el-color-warning-light-7);
  border-radius: 3px;
  color: var(--el-color-warning-dark-2);
}
</style>
