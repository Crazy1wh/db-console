# db-console

一个可自托管的 SQLite Web 数据库管理器 MVP。后端使用 FastAPI、Pydantic 和 Python `sqlite3`，前端使用 Vue 3、Vite、TypeScript、Element Plus 和 vxe-table。生产环境由 FastAPI 直接托管前端 `dist`，不使用 Jinja2。

## 功能

- 仅发现 `DB_ROOT` 内的 `.db`、`.sqlite`、`.sqlite3` 文件，解析真实路径以阻止路径穿越。
- 数据库创建、删除（二次确认）、文件/表/总行数统计。
- 表列表、创建、删除（二次确认）、字段结构和索引查看。
- 行数据远程分页、全列搜索、排序、列选择和组合筛选。
- 筛选运算符：`contains`、`equals`、`not equals`、`>`、`>=`、`<`、`<=`、`NULL`、`NOT NULL`。
- 行增删改优先使用完整主键；无主键表使用 SQLite `rowid`。
- SQL 单语句执行和参数绑定；`DROP TABLE`、`DROP DATABASE`、`VACUUM`、`ATTACH` 必须二次确认。
- vxe-table 固定表头、横向滚动、列拖宽、多选、双击编辑、NULL 弱化、长文本提示和 CSV 导出。
- 所有 API 使用统一 `{ "success": boolean, "data": ..., "error": ... }` 响应。

## Docker 启动

将 SQLite 文件放在 `./data` 中，然后运行：

```bash
docker compose up --build
```

打开 <http://localhost:8090>。容器以非 root 用户运行，`./data` 挂载为数据库根目录；请确保宿主机目录允许容器 UID `10001` 按所需方式读写。

如果宿主机 8090 已被占用，可使用其它宿主机端口，例如：`DB_CONSOLE_PORT=18090 docker compose up -d --build`，然后访问 `http://<主机局域网IP>:18090`。

环境变量：

| 名称 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_ROOT` | `/data`（容器） | 可访问 SQLite 文件的唯一根目录 |
| `CORS_ORIGINS` | `http://localhost:5173`（源码运行） | 逗号分隔的允许来源 |
| `PORT` | `8090`（容器） | Uvicorn 监听端口 |

## 本地开发

后端：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
DB_ROOT="$PWD/data" .venv/bin/uvicorn backend.main:app --reload --port 8090
```

前端（另一个终端）：

```bash
cd frontend
npm install
npm run dev
```

Vite 将 `/api` 代理到 `http://localhost:8090`。生产构建：

```bash
cd frontend && npm run build
cd .. && DB_ROOT="$PWD/data" .venv/bin/uvicorn backend.main:app --port 8090
```

## API 概览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET / POST | `/api/databases` | 扫描 / 创建数据库 |
| DELETE | `/api/databases/{db}?confirm=true` | 删除数据库 |
| GET | `/api/databases/{db}/stats` | 数据库统计 |
| GET / POST | `/api/databases/{db}/tables` | 表列表 / 创建表 |
| DELETE | `/api/databases/{db}/tables/{table}?confirm=true` | 删除表 |
| GET | `/api/databases/{db}/tables/{table}/structure` | 字段结构 |
| GET | `/api/databases/{db}/tables/{table}/indexes` | 索引 |
| GET | `/api/databases/{db}/tables/{table}/rows` | 分页、搜索、排序和筛选 |
| POST / PUT / DELETE | `/api/databases/{db}/tables/{table}/rows` | 行增删改 |
| POST | `/api/query` | 执行参数化 SQL |

筛选通过 URL 编码后的 JSON 数组传递，例如：

```text
filters=[{"column":"age","operator":">=","value":18},{"column":"email","operator":"NOT NULL"}]
```

参数化 SQL 示例：

```bash
curl -X POST http://localhost:8090/api/query \
  -H 'Content-Type: application/json' \
  -d '{"database":"sample.sqlite3","sql":"SELECT * FROM users WHERE id > ?","params":[10]}'
```

## 测试和验收

```bash
.venv/bin/pytest -q
cd frontend && npm run build
docker build -t db-console .
curl http://localhost:8090/api/health
```

测试覆盖数据库发现/创建/删除、路径穿越、扩展名限制、统计、表元数据、分页搜索排序筛选、PK/rowid CRUD、标识符注入、参数 SQL、危险语句确认、CORS 和错误响应格式。

## 安全边界

本工具面向受信任的单用户或内网环境，不包含身份认证。不要直接暴露到公网。SQL 控制台按设计允许修改数据库；二次确认只是防误操作，不是权限控制。所有数据库文件访问都受 `DB_ROOT` 限制，但运行进程仍应使用最小文件系统权限并做好数据备份。
