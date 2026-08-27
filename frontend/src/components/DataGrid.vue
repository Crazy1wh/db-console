<script setup lang="ts">
import { computed, ref } from 'vue'
import { Delete, Download, EditPen, Filter, Plus, Refresh, Search, View } from '@element-plus/icons-vue'
import type { ColumnInfo, FilterItem, RowsResult } from '../types'

const props = defineProps<{ result: RowsResult; structure: ColumnInfo[]; loading: boolean; search: string; filters: FilterItem[] }>()
const emit = defineEmits<{
  refresh: []; create: []; edit: [row: Record<string, unknown>]; remove: [rows: Record<string, unknown>[]]
  export: []; search: [value: string]; page: [page: number]; pageSize: [size: number]
  sort: [field: string, order: string]; filters: [filters: FilterItem[]]; columns: [columns: string[]]
}>()
const grid = ref<any>()
const filterVisible = ref(false)
const localSearch = ref(props.search)
const selectedColumns = ref<string[]>([])
const draftFilters = ref<FilterItem[]>([])
const operators = ['contains', 'equals', 'not equals', '>', '>=', '<', '<=', 'NULL', 'NOT NULL']
const displayColumns = computed(() => selectedColumns.value.length ? selectedColumns.value : props.result.columns)

function selection() { return grid.value?.getCheckboxRecords?.() || [] }
function addFilter() { draftFilters.value.push({ column: props.result.columns[0] || '', operator: 'contains', value: '' }) }
function openFilters() { draftFilters.value = props.filters.map(item => ({ ...item })); if (!draftFilters.value.length) addFilter(); filterVisible.value = true }
function applyFilters() { emit('filters', draftFilters.value.filter(item => item.column)); filterVisible.value = false }
function onSort({ field, order }: { field: string; order: string | null }) { emit('sort', field || '', order || 'asc') }
function formatCell({ cellValue }: { cellValue: unknown }) { return cellValue === null ? 'NULL' : String(cellValue) }
function cellClass({ row, column }: any) { return row[column.field] === null ? 'null-cell' : '' }
</script>

<template>
  <section class="data-pane">
    <div class="table-toolbar">
      <el-button-group>
        <el-button size="small" :icon="Refresh" @click="emit('refresh')">刷新</el-button>
        <el-button size="small" :icon="Plus" @click="emit('create')">新增</el-button>
        <el-button size="small" :icon="EditPen" :disabled="selection().length !== 1" @click="emit('edit', selection()[0])">编辑</el-button>
        <el-button size="small" :icon="Delete" :disabled="!selection().length" @click="emit('remove', selection())">删除</el-button>
      </el-button-group>
      <el-input v-model="localSearch" class="data-search" size="small" clearable placeholder="搜索所有列" :prefix-icon="Search" @keyup.enter="emit('search', localSearch)" @clear="emit('search', '')" />
      <el-button size="small" :icon="Filter" @click="openFilters">筛选 <span v-if="filters.length">({{ filters.length }})</span></el-button>
      <el-popover trigger="click" width="230">
        <template #reference><el-button size="small" :icon="View">列</el-button></template>
        <el-checkbox-group v-model="selectedColumns" class="column-picker" @change="emit('columns', selectedColumns)">
          <el-checkbox v-for="column in result.columns" :key="column" :value="column">{{ column }}</el-checkbox>
        </el-checkbox-group>
      </el-popover>
      <span class="toolbar-spacer" />
      <el-button size="small" :icon="Download" @click="emit('export')">CSV</el-button>
    </div>
    <div class="grid-wrap">
      <vxe-grid
        ref="grid" :loading="loading" :data="result.rows" height="100%" border stripe show-overflow="title"
        :row-config="{ isHover: true }" :column-config="{ resizable: true, minWidth: 100 }"
        :sort-config="{ remote: true }" :checkbox-config="{ highlight: true }" :cell-class-name="cellClass"
        @sort-change="onSort" @cell-dblclick="({ row }: any) => emit('edit', row)"
      >
        <vxe-column type="checkbox" width="42" fixed="left" />
        <vxe-column v-if="result.identity_type === 'rowid'" field="__rowid__" title="rowid" width="82" sortable :formatter="formatCell" />
        <vxe-column v-for="column in displayColumns" :key="column" :field="column" :title="column" min-width="130" sortable :formatter="formatCell" />
      </vxe-grid>
    </div>
    <div class="pager-bar">
      <span>{{ result.total.toLocaleString() }} rows</span>
      <el-pagination
        small background layout="sizes, prev, pager, next" :total="result.total" :current-page="result.page"
        :page-size="result.page_size" :page-sizes="[25, 50, 100, 200, 500]"
        @current-change="(value: number) => emit('page', value)" @size-change="(value: number) => emit('pageSize', value)"
      />
    </div>
    <el-drawer v-model="filterVisible" title="列筛选" size="460px">
      <div v-for="(item, index) in draftFilters" :key="index" class="filter-line">
        <el-select v-model="item.column" size="small"><el-option v-for="column in result.columns" :key="column" :label="column" :value="column" /></el-select>
        <el-select v-model="item.operator" size="small"><el-option v-for="operator in operators" :key="operator" :label="operator" :value="operator" /></el-select>
        <el-input v-if="!['NULL', 'NOT NULL'].includes(item.operator)" v-model="item.value" size="small" placeholder="值" />
        <el-button text type="danger" :icon="Delete" @click="draftFilters.splice(index, 1)" />
      </div>
      <el-button size="small" :icon="Plus" @click="addFilter">添加条件</el-button>
      <template #footer><el-button @click="draftFilters = []; applyFilters()">清空</el-button><el-button type="primary" @click="applyFilters">应用</el-button></template>
    </el-drawer>
  </section>
</template>
