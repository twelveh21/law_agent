本目录是项目根目录下的 Chroma 本地向量数据库，保存法律知识库的向量索引及元数据；其中的 UUID 子目录和 chroma.sqlite3 等属于 Chroma 自己管理的数据库文件。app/common/path.py 默认将 CHROMA_DIR 指向这里（环境变量 CHROMA_PATH 可覆盖）。不要手工编辑、移动或删除内部文件；法律文本更新后应通过知识库构建脚本重新索引。
