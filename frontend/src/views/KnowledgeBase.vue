<template>
  <div class="kb-page">
    <header class="page-header">
      <el-button @click="$router.push('/')" type="text">← 返回聊天</el-button>
      <h2>📚 知识库管理</h2>
      <el-button type="primary" @click="showAddDialog = true">+ 添加知识</el-button>
    </header>

    <el-input
      v-model="searchKeyword"
      placeholder="搜索知识库..."
      clearable
      @keyup.enter="search"
      style="margin-bottom: 16px;"
    >
      <template #prefix>🔍</template>
    </el-input>

    <div class="kb-grid">
      <div v-for="item in items" :key="item.id || item.question" class="kb-card">
        <div class="kb-category">{{ item.category || '未分类' }}</div>
        <div class="kb-question">Q: {{ item.question }}</div>
        <div class="kb-answer">A: {{ item.answer }}</div>
        <div class="kb-score" v-if="item.score">相似度: {{ (item.score * 100).toFixed(0) }}%</div>
      </div>
    </div>

    <!-- 添加知识对话框 -->
    <el-dialog v-model="showAddDialog" title="添加知识" width="500px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="addForm.category" placeholder="选择分类" clearable>
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题">
          <el-input v-model="addForm.question" type="textarea" :rows="2" placeholder="输入常见问题" />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="addForm.answer" type="textarea" :rows="4" placeholder="输入答案" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="addForm.keywords" placeholder="空格分隔" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="addKnowledge" :loading="adding">添加</el-button>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const searchKeyword = ref('')
const items = ref<any[]>([])
const categories = ref<string[]>([])
const showAddDialog = ref(false)
const adding = ref(false)

const addForm = reactive({
  category: '',
  question: '',
  answer: '',
  keywords: '',
})

async function search() {
  if (!searchKeyword.value) {
    items.value = []
    return
  }
  try {
    const data = await request.post('/api/v1/knowledge/search', {
      query: searchKeyword.value,
      top_k: 10,
    })
    items.value = data.results || []
  } catch (e) {
    console.error('搜索失败:', e)
  }
}

async function addKnowledge() {
  if (!addForm.question || !addForm.answer) return
  adding.value = true
  try {
    await request.post('/api/v1/knowledge/add', { ...addForm })
    showAddDialog.value = false
    addForm.category = ''
    addForm.question = ''
    addForm.answer = ''
    addForm.keywords = ''
    searchKeyword.value = addForm.question
    await search()
  } catch (e) {
    console.error('添加失败:', e)
  } finally {
    adding.value = false
  }
}

async function loadCategories() {
  try {
    const data = await request.get('/api/v1/knowledge/categories')
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
}
.kb-category {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  background: #e8f5e9;
  color: #4caf50;
  border-radius: 10px;
  margin-bottom: 8px;
}
.kb-question { font-weight: 600; margin-bottom: 6px; color: #333; }
.kb-answer { font-size: 14px; color: #666; line-height: 1.6; }
.kb-score { font-size: 11px; color: #999; margin-top: 8px; }
</style>
