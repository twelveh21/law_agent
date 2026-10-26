本目录放可单独运行的项目运维/数据处理脚本。build_knowledge_base.py 构建本地法律知识库；convert_pdf.py 批量提取 PDF 文本；watchdog_service.py 监控 input 并处理新文件；__init__.py 使脚本目录也可作为 Python 包导入。运行脚本前确认虚拟环境、.env、输入路径和目标数据库正确，避免覆盖不该改的数据。
