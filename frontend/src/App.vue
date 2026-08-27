<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Connection, Delete, Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, ApiError, enc } from './api'
import DatabaseTree from './components/DatabaseTree.vue'
import DataGrid from './components/DataGrid.vue'
import RowDrawer from './components/RowDrawer.vue'
import type { ColumnInfo, DatabaseInfo, DatabaseStats, FilterItem, IndexInfo, RowsResult, TableInfo } from './types'

const databases = ref<DatabaseInfo[]>([])
const tables = reactive<Record<string, TableInfo[]>>({})
const activeDatabase = ref('')
const activeTable = ref('')
const activeTab = ref('data')
const stats = ref<DatabaseStats | null>(null)
const structure = ref<ColumnInfo[]>([])
const indexes = ref<IndexInfo[]>([])
const rows = ref<RowsResult>({ rows: [], columns: [], total: 0, page: 1, page_size: 50, identity_type: 'primary_key', primary_keys: [] })
const loading = ref(false)
const search = ref('')
const sortBy = ref('')
const sortOrder = ref('asc')
const filters = ref<FilterItem[]>([])
const visibleColumns = ref<string[]>([])
const drawerOpen = ref(false)
const drawerMode = ref<'create' | 'edit'>('create')
const editRow = ref<Record<string, unknown> | null>(null)
const saving = ref(false)
const sql = ref('SELECT name, type, sql\nFROM sqlite_master\nORDER BY type, name;')
const sqlResult = ref<{ columns: string[]; rows: Record<string, unknown>[]; affected_rows: number | null; duration_ms: number } | null>(null)
const sqlRunning = ref(false)
const title = computed(() => activeTable.value ? `${activeDatabase.value} / ${activeTable.value}` : activeDatabase.value || 'db-console')

function showError(error: unknown) {
  ElMessage.error(error instanceof Error ? error.message : '操作失败')
}

async function loadDatabases() {
  try {
    databases.value = await api<DatabaseInfo[]>('/databases')
    for (const db of databases.value) await loadTables(db.name)
  } catch (error) { showError(error) }
}
async function loadTables(database: string) {
  tables[database] = await api<TableInfo[]>(`/databases/${enc(database)}/tables`)
}
async function selectDatabase(database: string) {
  activeDatabase.value = database; activeTable.value = ''; stats.value = null
  try { stats.value = await api<DatabaseStats>(`/databases/${enc(database)}/stats`) } catch (error) { showError(error) }
}
async function selectTable(database: string, table: string) {
  activeDatabase.value = database; activeTable.value = table; activeTab.value = 'data'
  search.value = ''; filters.value = []; sortBy.value = ''; visibleColumns.value = []; rows.value.page = 1
  loading.value = true
  try {
    ;[structure.value, indexes.value] = await Promise.all([
      api<ColumnInfo[]>(`/databases/${enc(database)}/tables/${enc(table)}/structure`),
      api<IndexInfo[]>(`/databases/${enc(database)}/tables/${enc(table)}/indexes`)
    ])
    await loadRows()
  } catch (error) { showError(error) } finally { loading.value = false }
}
async function loadRows() {
  if (!activeDatabase.value || !activeTable.value) return
  loading.value = true
  const params = new URLSearchParams({ page: String(rows.value.page), page_size: String(rows.value.page_size), sort_order: sortOrder.value })
  if (search.value) params.set('search', search.value)
  if (sortBy.value) params.set('sort_by', sortBy.value)
  if (visibleColumns.value.length) params.set('columns', visibleColumns.value.join(','))
  if (filters.value.length) params.set('filters', JSON.stringify(filters.value))
  try { rows.value = await api<RowsResult>(`/databases/${enc(activeDatabase.value)}/tables/${enc(activeTable.value)}/rows?${params}`) }
  catch (error) { showError(error) } finally { loading.value = false }
}
function identityFor(row: Record<string, unknown>) {
  if (rows.value.identity_type === 'rowid') return { rowid: row.__rowid__ }
  return Object.fromEntries(rows.value.primary_keys.map(key => [key, row[key]]))
}
function openCreate() { drawerMode.value = 'create'; editRow.value = null; drawerOpen.value = true }
function openEdit(row: Record<string, unknown>) { drawerMode.value = 'edit'; editRow.value = row; drawerOpen.value = true }
async function saveRow(values: Record<string, unknown>) {
  saving.value = true
  try {
    const path = `/databases/${enc(activeDatabase.value)}/tables/${enc(activeTable.value)}/rows`
    if (drawerMode.value === 'create') await api(path, { method: 'POST', body: JSON.stringify({ values }) })
    else await api(path, { method: 'PUT', body: JSON.stringify({ identity: identityFor(editRow.value!), values }) })
    drawerOpen.value = false; ElMessage.success('已保存'); await Promise.all([loadRows(), loadTables(activeDatabase.value)])
  } catch (error) { showError(error) } finally { saving.value = false }
}
async function deleteRows(selected: Record<string, unknown>[]) {
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selected.length} 行？此操作不可撤销。`, '删除行', { type: 'warning', confirmButtonText: '删除' })
    const path = `/databases/${enc(activeDatabase.value)}/tables/${enc(activeTable.value)}/rows`
    for (const row of selected) await api(path, { method: 'DELETE', body: JSON.stringify({ identity: identityFor(row) }) })
    ElMessage.success(`已删除 ${selected.length} 行`); await Promise.all([loadRows(), loadTables(activeDatabase.value)])
  } catch (error) { if (error !== 'cancel' && error !== 'close') showError(error) }
}
async function createDatabase() {
  try {
    const { value } = await ElMessageBox.prompt('输入宿主机路径或容器内路径，例如 /root/dev/car/data/car.db', '添加数据库', { inputPlaceholder: '/root/dev/project/data/app.db', inputPattern: /\.(db|sqlite|sqlite3)$/i, inputErrorMessage: '路径必须指向 .db、.sqlite 或 .sqlite3 文件' })
    const added = await api<{ name: string }>('/databases/register', { method: 'POST', body: JSON.stringify({ path: value }) }); await loadDatabases(); await selectDatabase(added.name)
  } catch (error) { if (error !== 'cancel' && error !== 'close') showError(error) }
}
async function deleteDatabase() {
  if (!activeDatabase.value) return
  try {
    await ElMessageBox.confirm(`永久删除数据库 ${activeDatabase.value}？`, '危险操作', { type: 'error', confirmButtonText: '确认删除' })
    await api(`/databases/${enc(activeDatabase.value)}?confirm=true`, { method: 'DELETE' })
    activeDatabase.value = ''; activeTable.value = ''; stats.value = null; await loadDatabases()
  } catch (error) { if (error !== 'cancel' && error !== 'close') showError(error) }
}
async function createTable() {
  if (!activeDatabase.value) return
  try {
    const { value } = await ElMessageBox.prompt('输入表名（默认创建 id INTEGER PRIMARY KEY）', '新建表', { inputPattern: /\S+/, inputErrorMessage: '请输入表名' })
    await api(`/databases/${enc(activeDatabase.value)}/tables`, { method: 'POST', body: JSON.stringify({ name: value, columns: [{ name: 'id', type: 'INTEGER', primary_key: true }] }) })
    await loadTables(activeDatabase.value); await selectTable(activeDatabase.value, value)
  } catch (error) { if (error !== 'cancel' && error !== 'close') showError(error) }
}
async function deleteTable() {
  if (!activeTable.value) return
  try {
    await ElMessageBox.confirm(`永久删除表 ${activeTable.value} 及其中全部数据？`, '危险操作', { type: 'error', confirmButtonText: '确认删除' })
    await api(`/databases/${enc(activeDatabase.value)}/tables/${enc(activeTable.value)}?confirm=true`, { method: 'DELETE' })
    activeTable.value = ''; await loadTables(activeDatabase.value); await selectDatabase(activeDatabase.value)
  } catch (error) { if (error !== 'cancel' && error !== 'close') showError(error) }
}
async function runSql(confirm = false) {
  if (!activeDatabase.value) return ElMessage.warning('请先选择数据库')
  sqlRunning.value = true
  try {
    sqlResult.value = await api('/query', { method: 'POST', body: JSON.stringify({ database: activeDatabase.value, sql: sql.value, confirm }) })
    ElMessage.success(`执行完成 · ${sqlResult.value?.duration_ms ?? 0} ms`); await loadTables(activeDatabase.value)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'CONFIRMATION_REQUIRED') {
      try { await ElMessageBox.confirm('该语句包含 DROP TABLE / DROP DATABASE / VACUUM / ATTACH，确认继续？', '二次确认', { type: 'warning' }); await runSql(true) }
      catch (nested) { if (nested !== 'cancel' && nested !== 'close') showError(nested) }
    } else showError(error)
  } finally { sqlRunning.value = false }
}
async function exportCsv() {
  if (!rows.value.total) return
  try {
    const all: Record<string, unknown>[] = []
    const totalPages = Math.ceil(rows.value.total / 500)
    for (let page = 1; page <= totalPages; page++) {
      const params = new URLSearchParams({ page: String(page), page_size: '500', sort_order: sortOrder.value })
      if (search.value) params.set('search', search.value)
      if (sortBy.value) params.set('sort_by', sortBy.value)
      if (visibleColumns.value.length) params.set('columns', visibleColumns.value.join(','))
      if (filters.value.length) params.set('filters', JSON.stringify(filters.value))
      const chunk = await api<RowsResult>(`/databases/${enc(activeDatabase.value)}/tables/${enc(activeTable.value)}/rows?${params}`); all.push(...chunk.rows)
    }
    const columns = rows.value.columns
    const quote = (value: unknown) => value === null ? '' : `"${String(value).replace(/"/g, '""')}"`
    const csv = '\ufeff' + [columns.map(quote).join(','), ...all.map(row => columns.map(column => quote(row[column])).join(','))].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); const link = document.createElement('a')
    link.href = url; link.download = `${activeTable.value}.csv`; link.click(); URL.revokeObjectURL(url)
  } catch (error) { showError(error) }
}
onMounted(loadDatabases)
</script>

<template>
  <div class="shell">
    <header class="titlebar"><Connection class="brand-icon" /><strong>db-console</strong><span class="crumb">{{ title }}</span><span class="title-spacer" /><span class="connection-state">● SQLite</span></header>
    <div class="workspace">
      <DatabaseTree :databases="databases" :tables="tables" :active-database="activeDatabase" :active-table="activeTable" @select-database="selectDatabase" @select-table="selectTable" @refresh="loadDatabases" @create-database="createDatabase" />
      <main class="main-panel">
        <template v-if="activeTable">
          <div class="object-header">
            <div><span class="object-kind">TABLE</span><strong>{{ activeTable }}</strong><span class="muted">{{ rows.total.toLocaleString() }} rows</span></div>
            <el-button size="small" text type="danger" :icon="Delete" @click="deleteTable">删除表</el-button>
          </div>
          <el-tabs v-model="activeTab" class="main-tabs">
            <el-tab-pane label="数据" name="data">
              <DataGrid :result="rows" :structure="structure" :loading="loading" :search="search" :filters="filters" @refresh="loadRows" @create="openCreate" @edit="openEdit" @remove="deleteRows" @export="exportCsv" @search="value => { search = value; rows.page = 1; loadRows() }" @page="value => { rows.page = value; loadRows() }" @page-size="value => { rows.page_size = value; rows.page = 1; loadRows() }" @sort="(field, order) => { sortBy = field; sortOrder = order; loadRows() }" @filters="value => { filters = value; rows.page = 1; loadRows() }" @columns="value => { visibleColumns = value; loadRows() }" />
            </el-tab-pane>
            <el-tab-pane label="结构" name="structure">
              <el-table :data="structure" height="100%" size="small" border><el-table-column prop="cid" label="#" width="50" /><el-table-column prop="name" label="列名" min-width="180" /><el-table-column prop="type" label="类型" width="150" /><el-table-column label="非空" width="80"><template #default="{ row }">{{ row.not_null ? 'YES' : '' }}</template></el-table-column><el-table-column label="主键" width="80"><template #default="{ row }">{{ row.primary_key ? `PK ${row.pk_position}` : '' }}</template></el-table-column><el-table-column prop="default" label="默认值" min-width="160" /></el-table>
            </el-tab-pane>
            <el-tab-pane label="索引" name="indexes">
              <el-table :data="indexes" height="100%" size="small" border><el-table-column prop="name" label="索引名" min-width="220" /><el-table-column label="列" min-width="220"><template #default="{ row }">{{ row.columns.join(', ') }}</template></el-table-column><el-table-column label="唯一" width="80"><template #default="{ row }">{{ row.unique ? 'YES' : '' }}</template></el-table-column><el-table-column prop="origin" label="来源" width="100" /><el-table-column label="部分索引" width="100"><template #default="{ row }">{{ row.partial ? 'YES' : '' }}</template></el-table-column></el-table>
            </el-tab-pane>
            <el-tab-pane label="SQL" name="sql">
              <div class="sql-pane"><div class="sql-toolbar"><el-button type="primary" size="small" :icon="VideoPlay" :loading="sqlRunning" @click="runSql(false)">执行</el-button><span>参数占位符请使用 SQLite <code>?</code>，当前控制台执行单条语句</span></div><el-input v-model="sql" type="textarea" resize="none" class="sql-editor" /><div class="sql-result-header">结果 <span v-if="sqlResult">· {{ sqlResult.affected_rows ?? sqlResult.rows.length }} rows · {{ sqlResult.duration_ms }} ms</span></div><el-table v-if="sqlResult" :data="sqlResult.rows" height="100%" size="small" border><el-table-column v-for="column in sqlResult.columns" :key="column" :prop="column" :label="column" min-width="140" show-overflow-tooltip /></el-table></div>
            </el-tab-pane>
          </el-tabs>
        </template>
        <template v-else-if="activeDatabase && stats">
          <div class="object-header"><div><span class="object-kind">DATABASE</span><strong>{{ activeDatabase }}</strong></div><div><el-button size="small" :icon="Plus" @click="createTable">新建表</el-button><el-button size="small" :icon="Refresh" @click="selectDatabase(activeDatabase)">刷新</el-button><el-button size="small" text type="danger" :icon="Delete" @click="deleteDatabase">删除数据库</el-button></div></div>
          <section class="overview"><h2>数据库概览</h2><dl class="stats-list"><div><dt>表</dt><dd>{{ stats.table_count }}</dd></div><div><dt>总行数</dt><dd>{{ stats.row_count.toLocaleString() }}</dd></div><div><dt>文件大小</dt><dd>{{ (stats.size_bytes / 1024).toFixed(1) }} KB</dd></div><div><dt>分配空间</dt><dd>{{ (stats.allocated_bytes / 1024).toFixed(1) }} KB</dd></div></dl><h3>表统计</h3><el-table :data="stats.tables" size="small" border max-height="420"><el-table-column prop="table" label="表名" min-width="260" /><el-table-column prop="row_count" label="行数" width="160" /></el-table></section>
        </template>
        <div v-else class="welcome"><Connection /><h1>db-console</h1><p>从左侧选择数据库，或创建一个新的 SQLite 数据库。</p><el-button type="primary" :icon="Plus" @click="createDatabase">新建数据库</el-button></div>
      </main>
    </div>
    <footer class="statusbar"><span>SQLite</span><span>DB_ROOT sandbox</span><span class="title-spacer" /><span>{{ activeDatabase || '未连接' }}</span></footer>
    <RowDrawer v-model="drawerOpen" :mode="drawerMode" :columns="structure" :row="editRow" :saving="saving" @save="saveRow" />
  </div>
</template>
