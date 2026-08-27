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

确认 Compose 中配置的 SQLite 目录存在，然后运行：

```bash
docker compose up --build
```

打开 <http://localhost:6080>。首次登录默认账号为 `admin`，默认密码为 `admin123`。

网页左侧“添加数据库”支持两种路径：宿主机路径（例如 `/root/dev/car/data/car.db`）和容器路径（例如 `/external/car/data/car.db`）。宿主机路径会根据 `DB_HOST_ROOT` 自动映射到容器内的 `/external`，数据库文件不会复制到 Docker 镜像。

宿主机端口默认是 6080，可通过 `DB_CONSOLE_PORT` 修改。局域网访问地址为 `http://<主机局域网IP>:6080`。

环境变量：

| 名称 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_ROOT` | `/data`（容器） | 可访问 SQLite 文件的唯一根目录 |
| `DB_HOST_ROOT` | 空 | 宿主机外部数据库根目录，例如 `/root/dev` |
| `DB_EXTERNAL_ROOT` | `/external` | 容器内外部数据库映射根目录 |
| `DB_CONSOLE_USER` | `10001:10001` | 容器运行 UID:GID；宿主 SQLite 目录不可写时可改为 `0:0` |
| `CORS_ORIGINS` | `http://localhost:5173`（源码运行） | 逗号分隔的允许来源 |
| `PORT` | `8090`（容器） | Uvicorn 监听端口 |
| `AUTH_USERNAME` | `admin` | 登录用户名 |
| `AUTH_PASSWORD` | `admin123` | 登录密码，生产环境必须修改 |
| `SESSION_SECRET` | 内置默认值 | Cookie 签名密钥，生产环境必须修改 |

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
| POST | `/api/databases/register` | 注册一个已挂载的 SQLite 文件路径 |

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

本工具面向受信任的单用户或内网环境。已提供基于环境变量的简单登录保护，但不是完整的多用户权限系统，不要直接暴露到公网。SQL 控制台按设计允许修改数据库；二次确认只是防误操作，不是权限控制。所有数据库文件访问都受 `DB_ROOT` 限制，但运行进程仍应使用最小文件系统权限并做好数据备份。

## 开源许可

本项目以 MIT License 发布，详见 [LICENSE](LICENSE)。欢迎提交 Issue 和 Pull Request。
