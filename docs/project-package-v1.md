# MluaScript 项目包 v1

项目包是脚本、Blockly 源文件、Maa 资源、普通资源和自定义模型的最小分发单元。
开发时使用目录，发布时打包为确定性的 `.mlspkg` ZIP 文件。

## 目录布局

```text
project/
  mluascript.yaml
  scripts/
    main.lua
    tasks/
    lib/
  blockly/
    main.xml
  resources/
    maa/
    assets/
  models/
    ocr/
    nnd/
  templates/
  README.md
```

`scripts/` 是 Lua `require` 的根目录；`resources/maa/` 是 Maa 资源目录。
`resources/assets/` 供项目普通资源使用，`models/` 单独存放模型，避免把模型和 Maa
资源目录混在一起。

## Manifest

`mluascript.yaml` 使用 `mluascript.package/v1` schema：

```yaml
schema: mluascript.package/v1
package:
  id: com.example.daily-task
  name: 每日任务
  version: 0.1.0
runtime:
  lua: "5.4"
  mluascript: ">=1.0.0"
entrypoints:
  main:
    name: 主入口
    script: scripts/main.lua
    blockly: blockly/main.xml
    models:
      ocr: chinese-v4
resources:
  maa: resources/maa
  assets: resources/assets
models:
  chinese-v4:
    type: maa.ocr
    path: models/ocr/chinese-v4
capabilities:
  device: true
  network: false
  llm: false
  package_files: read
extensions: {}
```

manifest 中的路径只能是项目内相对路径。所有 entrypoint、resource 和 model 引用在
打包前都会检查存在性；模型必须已存在于项目目录中。

## 打包规则

- ZIP 根目录直接放置 manifest 和项目文件，不再套一层项目目录。
- 文件按 POSIX 路径排序，固定 ZIP 时间戳和文件属性，保证同一输入得到同一包内容。
- `META-INF/files.sha256` 保存包内文件清单；构建结果另外返回整个 `.mlspkg` 的 SHA-256。
- `.git`、`.mluascript`、`__pycache__` 和 `.venv` 不进入包。
- 拒绝绝对路径、`..` 路径穿越、符号链接和大小写冲突文件。
- 构建产物放在宿主机管理的 `.mluascript/builds/`，不会写回项目目录。

## Web 工作流

Web 配置中的 `WebServerConfig.project_roots` 控制可创建和发现的项目根目录，默认是
`./projects`。前端统一使用“编辑器”工作区：manifest 声明的 Blockly XML 由 Blockly
编辑，其他 UTF-8 文件由带语法高亮的文本编辑器处理，二进制资源和模型只上传、下载，
不会作为文本载入内存。工作区同时提供 manifest 校验、打包和下载；项目 API 只接受
服务端生成的 `projectKey`，不接受任意宿主机路径。

`WebServerConfig.enabled` 控制程序启动时是否自动启动 Web 服务。即使自动启动关闭，
仍可在 TUI 的 Web 页面手动启动或关闭服务；程序退出时会统一等待 Web 服务线程结束。

v1 的自定义模型采用“随包分发”策略：模型必须随 `.mlspkg` 一起提供，运行时只读，
不自动下载、不访问模型仓库，也不拆分外部依赖。超大模型的缓存、下载、引用计数和
分层包留到后续版本。
