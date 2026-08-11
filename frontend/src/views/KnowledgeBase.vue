<template>
  <div class="kb-page">
    <header class="page-header">
      <h2>📚 知识库管理</h2>
      <el-button type="primary" @click="showAddDialog = true">+ 添加知识</el-button>
    </header>

    <el-input
      v-model="searchKeyword"
      placeholder="搜索知识库..."
      clearable
      @keyup.enter="search"
      @clear="onClear"
      style="margin-bottom: 16px;"
    >
      <template #prefix>🔍</template>
    </el-input>

    <!-- 空状态 -->
    <div v-if="searched && items.length === 0" class="empty-state">
      <div class="empty-icon">📭</div>
      <p class="empty-title">未找到相关知识</p>
      <p class="empty-hint">尝试其他关键词搜索，或添加新的知识条目</p>
      <el-button type="primary" @click="showAddDialog = true">+ 添加知识</el-button>
    </div>

    <!-- 未搜索状态 -->
    <div v-if="!searched && items.length === 0" class="empty-state">
      <div class="empty-icon">🔍</div>
      <p class="empty-title">搜索知识库内容</p>
      <p class="empty-hint">输入关键词搜索已录入的常见问题与答案</p>
    </div>

    <div class="kb-grid">
      <div v-for="item in items" :key="item.id || item.question" class="kb-card">
        <div class="kb-header">
          <span class="kb-category">{{ item.category || '未分类' }}</span>
          <span class="kb-actions">
            <el-button size="small" text title="删除知识条目" aria-label="删除知识条目" @click="deleteItem(item)">🗑️</el-button>
          </span>
        </div>
        <div class="kb-question">Q: {{ item.question }}</div>
        <div class="kb-answer">A: {{ item.answer }}</div>
        <div
          v-if="item.score != null"
          class="kb-score"
          :class="scoreClass(item.score)"
        >
          相似度: {{ (item.score * 100).toFixed(0) }}%
        </div>
      </div>
    </div>

    <!-- 添加知识对话框 -->
    <el-dialog v-model="showAddDialog" title="添加知识" width="500px" @closed="resetForm">
      <el-form ref="formRef" :model="addForm" :rules="formRules" label-width="80px">
        <el-form-item label="分类" prop="category">
          <el-select v-model="addForm.category" placeholder="选择分类" clearable>
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题" prop="question">
          <el-input
            v-model="addForm.question"
            type="textarea"
            :rows="2"
            placeholder="输入常见问题"
          />
        </el-form-item>
        <el-form-item label="答案" prop="answer">
          <el-input
            v-model="addForm.answer"
            type="textarea"
            :rows="4"
            placeholder="输入答案"
          />
        </el-form-item>
        <el-form-item label="关键词" prop="keywords">
          <el-input v-model="addForm.keywords" placeholder="空格分隔" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="addKnowledge" :loading="adding">
            添加
          </el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
import type { FormInstance, FormRules } from 'element-plus'

const searchKeyword = ref('')
const items = ref<any[]>([])
const categories = ref<string[]>([])
const showAddDialog = ref(false)
const adding = ref(false)
const searched = ref(false)
const formRef = ref<FormInstance>()

const addForm = reactive({
  category: '',
  question: '',
  answer: '',
  keywords: '',
})

const formRules: FormRules = {
  question: [{ required: true, message: '请输入问题', trigger: 'blur' }],
  answer: [{ required: true, message: '请输入答案', trigger: 'blur' }],
}

async function search() {
  if (!searchKeyword.value.trim()) return
  searched.value = true
  try {
    const data = await request.post('/api/v1/knowledge/search', {
      query: searchKeyword.value,
      top_k: 10,
    }) as any
    items.value = data.results || []
  } catch (e) {
    console.error('搜索失败:', e)
  }
}

function onClear() {
  searched.value = false
}

function scoreClass(score: number) {
  if (score >= 0.8) return 'score-high'
  if (score >= 0.6) return 'score-mid'
  return 'score-low'
}

async function deleteItem(item: any) {
  try {
    await ElMessageBox.confirm('确定要删除该知识条目吗？', '确认删除', { type: 'warning' })
    const res = (await request.delete(`/api/v1/knowledge/${item.id}`)) as any
    if (res && res.success === false) {
      ElMessage.error(res.message || '删除失败')
      return
    }
    ElMessage.success('已删除')
    if (searchKeyword.value) await search()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error('删除失败')
    console.error('删除失败:', e)
  }
}

async function addKnowledge() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return // 校验未通过，不提交
  }

  adding.value = true
  try {
    await request.post('/api/v1/knowledge/add', { ...addForm })
    showAddDialog.value = false
    searchKeyword.value = addForm.question
    await search()
  } catch (e) {
    console.error('添加失败:', e)
  } finally {
    adding.value = false
  }
}

function resetForm() {
  addForm.category = ''
  addForm.question = ''
  addForm.answer = ''
  addForm.keywords = ''
  formRef.value?.clearValidate()
}

async function loadCategories() {
  try {
    const data = await request.get('/api/v1/knowledge/categories') as any
    categories.value = data.categories || []
  } catch (e) {
    console.error('加载分类失败:', e)
  }
}

onMounted(loadCategories)
</script>

<style scoped>
.kb-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.page-header h2 { flex: 1; }

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #595959;
}
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-title { font-size: 16px; color: #666; margin-bottom: 6px; }
.empty-hint { font-size: 13px; margin-bottom: 16px; }

.kb-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kb-card {
  background: #fff;
  padding: 16px;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;
}
.kb-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.kb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.kb-category {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  background: #e8f5e9;
  color: #4caf50;
  border-radius: 10px;
}
.kb-actions {
  display: flex;
  gap: 4px;
  opacity: 0.3;
  transition: opacity 0.2s ease;
}
.kb-card:hover .kb-actions,
.kb-card:focus-within .kb-actions { opacity: 1; }
/* 触屏设备无 hover 态，操作按钮常驻可见（U9） */
@media (hover: none) {
  .kb-actions { opacity: 1; }
}

.kb-question { font-weight: 600; margin-bottom: 6px; color: #333; }
.kb-answer { font-size: 14px; color: #666; line-height: 1.6; }
.kb-score { font-size: 11px; margin-top: 8px; }
.kb-score.score-high { color: #4caf50; }
.kb-score.score-mid { color: #ff9800; }
.kb-score.score-low { color: #595959; }
</style>
