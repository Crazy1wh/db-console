<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { ColumnInfo } from '../types'

const props = defineProps<{ modelValue: boolean; mode: 'create' | 'edit'; columns: ColumnInfo[]; row: Record<string, unknown> | null; saving: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; save: [values: Record<string, unknown>] }>()
const form = reactive<Record<string, unknown>>({})
const nulls = reactive<Record<string, boolean>>({})
const editableColumns = computed(() => props.columns.filter(column => column.name !== '__rowid__'))

watch(() => [props.modelValue, props.row, props.mode] as const, () => {
  if (!props.modelValue) return
  for (const key of Object.keys(form)) delete form[key]
  for (const key of Object.keys(nulls)) delete nulls[key]
  for (const column of editableColumns.value) {
    const value = props.mode === 'edit' ? props.row?.[column.name] : undefined
    form[column.name] = value ?? ''
    nulls[column.name] = value === null
  }
}, { deep: true })

function save() {
  const values: Record<string, unknown> = {}
  for (const column of editableColumns.value) {
    if (props.mode === 'create' && form[column.name] === '' && !nulls[column.name]) continue
    let value = nulls[column.name] ? null : form[column.name]
    if (value !== null && value !== '' && /INT|REAL|NUMERIC|DECIMAL|FLOAT|DOUBLE/i.test(column.type)) value = Number(value)
    values[column.name] = value
  }
  emit('save', values)
}
</script>

<template>
  <el-drawer :model-value="modelValue" size="420px" :title="mode === 'create' ? '新增行' : '编辑行'" destroy-on-close @close="emit('update:modelValue', false)">
    <el-form label-position="top" size="small" class="row-form">
      <el-form-item v-for="column in editableColumns" :key="column.name">
        <template #label>
          <span>{{ column.name }}</span><span class="column-type">{{ column.type || 'ANY' }}{{ column.primary_key ? ' · PK' : '' }}</span>
        </template>
        <div class="field-line">
          <el-input v-if="/TEXT|CLOB|CHAR/i.test(column.type)" v-model="form[column.name]" type="textarea" :rows="2" :disabled="nulls[column.name]" />
          <el-input v-else v-model="form[column.name]" :disabled="nulls[column.name]" />
          <el-checkbox v-model="nulls[column.name]" label="NULL" :disabled="column.not_null" />
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-drawer>
</template>
