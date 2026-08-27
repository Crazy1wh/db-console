<script setup lang="ts">
import { computed, ref } from 'vue'
import { Coin, Plus, Refresh, Search } from '@element-plus/icons-vue'
import type { DatabaseInfo, TableInfo } from '../types'

const props = defineProps<{ databases: DatabaseInfo[]; tables: Record<string, TableInfo[]>; activeDatabase: string; activeTable: string }>()
const emit = defineEmits<{
  selectDatabase: [name: string]
  selectTable: [database: string, table: string]
  refresh: []
  createDatabase: []
}>()
const keyword = ref('')
const filtered = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return props.databases
  return props.databases.filter(db => db.name.toLowerCase().includes(needle) || (props.tables[db.name] || []).some(t => t.name.toLowerCase().includes(needle)))
})
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-title">
      <span>DATABASES</span>
      <div>
        <el-button text :icon="Plus" title="添加数据库路径" @click="emit('createDatabase')" />
        <el-button text :icon="Refresh" title="刷新" @click="emit('refresh')" />
      </div>
    </div>
    <el-input v-model="keyword" class="tree-search" size="small" placeholder="筛选数据库或表" :prefix-icon="Search" clearable />
    <div class="tree-scroll">
      <div v-for="db in filtered" :key="db.name" class="db-group">
        <button class="tree-row database" :class="{ active: activeDatabase === db.name && !activeTable }" @click="emit('selectDatabase', db.name)">
          <el-icon><Coin /></el-icon><span class="tree-name" :title="db.name">{{ db.name }}</span>
        </button>
        <button
          v-for="table in tables[db.name] || []" :key="`${db.name}/${table.name}`"
          class="tree-row table" :class="{ active: activeDatabase === db.name && activeTable === table.name }"
          @click="emit('selectTable', db.name, table.name)"
        >
          <span class="table-glyph">▦</span><span class="tree-name" :title="table.name">{{ table.name }}</span><span class="row-count">{{ table.row_count }}</span>
        </button>
      </div>
      <div v-if="!filtered.length" class="empty-tree">没有可用数据库</div>
    </div>
  </aside>
</template>
