# 律知：法律问答 Agent

这是一个基于 LangChain、FastAPI 和 Chroma 的中文法律信息问答项目。它可以检索本地法律文本、按需联网搜索，并以网页聊天界面提供服务。

## 本地运行

1. 安装 Python 3.13 和 uv。
2. 在项目根目录复制 `.env.example` 为 `.env`，填写 DashScope 和 Tavily 密钥。不要把 `.env` 上传到 GitHub。
3. 安装依赖：`uv sync`
4. 启动服务：`uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload`
5. 浏览器打开 `http://127.0.0.1:8001`

图片上传需要额外配置阿里云 OSS。`.env.example` 列出支持的环境变量。

## 在线演示

项目包含 Render Blueprint 配置。部署流程和免费服务的限制见 [DEPLOY_RENDER.md](DEPLOY_RENDER.md)。部署后前端和 API 共用一个网址。

## 隐私说明

不要把真实案件材料、身份证号、联系方式、合同原件或密钥提交到本仓库。`.gitignore` 排除了本地环境文件、数据库、会话缓存、笔记、个人输入/输出文件和归档。根目录 `chroma_db/` 与 `data/` 中保留的是用于演示的法律文本索引和公开法律文本。

会话 ID 只用于演示环境中的基本隔离，不等同于账号认证。请勿在公开演示服务中输入敏感个人或案件信息。

本项目提供法律信息检索与整理，不构成律师意见或正式法律服务。
