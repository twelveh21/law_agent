# 将法律 Agent 发布成可访问的网址

本项目的 FastAPI 已同时托管 `app/static` 前端和 `/api/v1` 接口，因此部署为一个 Python Web Service 即可。GitHub 用来保存代码，Render 负责运行应用；访问者只需要打开 Render 提供的网址。

## 发布前先检查

- 不要提交 `.env`、任何运行数据库、`app/chroma_db/`、`.langgraph_api/`、`data/notes/`、个人输入/输出/PDF 文件或 ZIP 归档。根目录 `.gitignore` 已排除这些内容；只保留核对过的根目录法律 Chroma 索引。
- 根目录 `chroma_db/` 是项目当前本地法律索引，含有 14 部法律文本的 1316 个切片，文件约 30 MB；部署配置选择其中有数据的 `langchain` 集合。不要把这个目录替换成含有个人文档的索引。
- Render 配置使用免费 Web Service。免费实例空闲后会休眠，运行时 SQLite、记忆和会话笔记是临时数据，服务重启/休眠回收后可能丢失。不要把免费部署当作长期保存用户会话的服务。
- 对外演示时不要上传身份证、联系方式、合同原件等敏感资料。图片上传需要 OSS 配置；当前上传对象以可访问 URL 交给模型，Bucket 访问策略应单独审查。
- 会话 ID 只用于基本会话隔离，不是账号登录。当前版本适合公开演示，不适合存储真实用户或案件资料。
- 对话和图片签名接口各自限制为每 IP 每分钟 10 次。限流保存在单个运行进程内，免费演示用来减轻误用，不是完整的反滥用或账号权限系统。

## 部署步骤

1. 检查 `.gitignore` 和待提交文件，确认 `.env`、本地数据库、`data/notes/`、`input/`、`output/`、`pdf/`、`archives/` 没有进入 Git。
2. 将项目推送到自己的 GitHub 仓库。仓库根目录必须保留 `pyproject.toml`、`uv.lock`、`render.yaml` 和 `.python-version`。
3. 在 Render 选择 **New → Blueprint**, 连接该 GitHub 仓库并应用 `render.yaml`。
4. 在 Render 提示时填写 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`TAVILY_API_KEY`。要开放图片上传，再填写 OSS 三项配置。
5. 等待首次部署完成，打开 Render 给出的 `onrender.com` 地址。前端和 API 同源，不需要单独改 API 地址或开放跨域。

## 免费演示的限制

Render 免费 Web Service 在空闲一段时间后会休眠，首次访问可能需要等待唤醒；免费服务没有持久磁盘，所以当前 SQLite 会话、记忆和笔记不能保证跨重启保存。若要给真实用户长期使用，需要升级为有持久存储的部署，并进一步加入用户身份认证、隐私隔离、备份和滥用控制。
