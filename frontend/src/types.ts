export interface DatabaseInfo { name: string; size_bytes: number; modified_at?: number }
export interface TableInfo { name: string; row_count: number }
export interface ColumnInfo {
  cid: number; name: string; type: string; not_null: boolean; default: unknown
  primary_key: boolean; pk_position: number
}
export interface IndexInfo { name: string; unique: boolean; origin: string; partial: boolean; columns: string[] }
export interface FilterItem { column: string; operator: string; value?: unknown }
export interface RowsResult {
  rows: Record<string, unknown>[]; columns: string[]; total: number; page: number; page_size: number
  identity_type: 'primary_key' | 'rowid'; primary_keys: string[]
}
export interface DatabaseStats {
  name: string; size_bytes: number; allocated_bytes: number; table_count: number; row_count: number
  tables: Array<{ table: string; row_count: number }>
}
