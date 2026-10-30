# 法律 Agent：第一次使用 Docker

当前配置运行一个应用容器，包含 FastAPI、前端和 stdio 法律 MCP 子进程。模型与 Tavily 仍通过外部 API 调用，不需要 GPU。PostgreSQL 和独立 Qdrant 服务将在后续阶段加入。

## 1. 安装与启动 Docker Desktop

Windows 官方安装说明：https://docs.docker.com/desktop/setup/install/windows-install/

选择与你电脑架构对应的版本；常见 Intel/AMD 电脑用 x86_64。按安装器提示准备 WSL 2，若系统要求重启，先保存工作。打开 Docker Desktop，等待引擎启动。安装完成后重新打开 PowerShell，再执行：

```powershell
docker version
docker compose version
```

`docker version` 应同时显示 Client 和 Server；只有 Client 或无法连接 daemon 表示引擎还没就绪。

## 2. 准备项目

在项目根目录运行。当前本地路径是 `D:\agent\tests`。

```powershell
Set-Location D:\agent\tests
```

保留现有 `.env`，不要用示例覆盖已有密钥。如果是新下载项目，可从 `.env.example` 复制并填写配置。至少提供 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`；联网 MCP 需要 `TAVILY_API_KEY`。图片上传需要原有 OSS 配置。

`.env` 由 Compose 在启动时读取，不进入镜像；不要把真实密钥写入 Dockerfile 或 compose.yaml。可通过容器环境访问这些配置，因此只给可信用户使用本机 Docker 权限。

## 3. 构建并启动

先停止原本运行的本地后端及入库脚本。本配置复用同一套数据库目录，嵌入式 Qdrant 不支持两个独立进程同时占用目录。

```powershell
docker compose up --build -d
```

首次构建会下载 Python 基础镜像和项目依赖。容器启动后浏览器访问：

http://127.0.0.1:8001

如果电脑的 8001 已被其他程序占用，可在当前 PowerShell 中设置：

```powershell
$env:LAW_HTTP_PORT = "8002"
docker compose up -d
```

随后访问 http://127.0.0.1:8002 。这里只绑定本机地址，不是公网发布。

## 4. 查看运行情况

```powershell
docker compose ps
docker compose logs -f app
```

日志中可以观察 Tavily MCP 和 Legal RAG MCP 是否连接成功。`Ctrl+C` 退出日志查看，不会停止后台容器。

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

健康接口只表示应用可响应，不代表每一个外部工具均可用；再发一次法律问题验证完整问答。

## 5. 数据在哪里

| 电脑上的目录 | 容器内目录 | 内容 |
| --- | --- | --- |
| `./db` | `/var/lib/law-agent/db` | 聊天检查点、Memory |
| `./data` | `/var/lib/law-agent/data` | 原始法律 TXT、本地 Qdrant、笔记 |
| `./chroma_db` | `/var/lib/law-agent/chroma` | 旧 Chroma 索引 |

这是 bind mount：容器直接访问这些电脑目录，而不是将数据复制进镜像。重建/删除应用容器不会删除这些目录；容器中的删除操作同样会改变电脑上的文件，重要资料请先备份。本次已验证当前数据在 Linux 容器中可启动，并通过法律 MCP 检索到了已导入法条；换版本或换数据后仍应检查兼容性。

当前配置读取 `.env` 中的 QDRANT_URL；为空时使用挂载目录中的本地 Qdrant。设置远程 URL 时使用远程库，不会自动迁移本地数据。

若在 Linux 机器运行，运行用户 UID 为 1000，需要确保挂载目录对该用户可写。

## 6. 更新代码与停止

代码变化后重新构建：

```powershell
docker compose up --build -d
```

停止并移除应用容器：

```powershell
docker compose down
```

挂载的电脑数据目录仍保留。仅修改 `.env` 时使用 `docker compose up -d --force-recreate`，确保环境重新注入。

## 7. 在容器环境中导入资料

避免另开进程直接打开同一个本地 Qdrant 目录。需要入库时，先停止应用，再用单次容器执行脚本：

```powershell
docker compose stop app
docker compose run --rm --no-deps app python -m scripts.ingest_qdrant /var/lib/law-agent/data/劳动合同法.txt
docker compose up -d
```

不要在应用仍占用本地库时直接运行独立入库进程。现有脚本用于 TXT 法律文件；更新文档后的旧切片清理尚未实现。

## 本次验证范围

2026-10-28 已实际完成：

- Docker 镜像构建成功，Linux 环境按 uv.lock 安装依赖。
- 容器 `law-agent-app-1` 启动，网页与健康接口可访问。
- Tavily MCP 与本地法律 RAG MCP 均发现工具并连接成功。
- 真实模型实际调用 `search_legal_knowledge`，返回第三十七条，并完成可选回答复核。
- 会话最终答案可读取，重启容器后仍保留；验证会话已单独删除。
- 强制重新创建容器后，db/data/chroma 三个挂载目录的验证文件仍在，验证文件随后清理。
- 应用以非 root 用户运行，镜像内没有 `/app/.env`。
- 现有 33 项本地测试通过。

首次容器启动前的数据库备份位于：`archives/before-docker-20261028-205402/`。没有推送 GitHub，也没有更新 Render。

## 新安装 Docker 后的终端路径问题

如果当前终端提示找不到 docker 或 docker-credential-desktop，先重新打开终端。若使用的是按用户安装的 Docker Desktop，也可仅对当前 PowerShell 补充路径：

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
```

然后再次运行 `docker compose up -d`。无需修改 Docker 凭据配置。
