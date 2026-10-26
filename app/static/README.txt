本目录是 FastAPI 实际提供给浏览器的前端静态资源。app/main.py 将该目录挂载到网站根路径；index.html、styles.css、app.js 是当前手工维护的法律 Agent 页面及交互逻辑。目录中的 _next、404、_not-found 等是框架导出的旧/生成资源，不是当前主要页面源码；其中带哈希的静态子目录由构建工具管理，不建议手工改动。
