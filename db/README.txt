本目录保存项目的 SQLite 持久化数据库，当前有 law.db 及运行时生成的 law.db-wal、law.db-shm。common/path.py 默认将 SQLite 主文件定位到这里（环境变量 LAW_DATABASE_PATH 可覆盖）。数据库内容由应用/SQLite 管理；不要手动删除 WAL 文件或直接编辑数据库，否则可能丢失对话检查点等数据。
