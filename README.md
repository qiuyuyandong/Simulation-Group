# Simulation-Group

仿真小组的协作仓库，用于保存果树建模代码、必要素材和项目说明。当前主要工作是生成单株苹果树、橙子树，在 Blender 中检查和调整模型，再导出对应的素材元数据。

日常建树从 `FruitTreesBuild/` 开始。`extension/` 是独立的 Blender 插件；旧框架、备份和检查结果暂时保留，后续逐步归档。

## 目录说明

| 路径 | 用途 | 使用约定 |
| --- | --- | --- |
| [FruitTreesBuild/](FruitTreesBuild/README.md) | 苹果树、橙子树生成与素材元数据导出 | 主要开发和使用入口 |
| [extension/](extension/spacetree-master/README.md) | 独立的 SCA Tree Generator 插件 | 在 Blender 界面中使用；与脚本建树工程分别维护 |
| `IAMPS2019-Procedural-Fruit-Tree-Rendering-Framework-master/` | 旧框架、历史场景脚本、示例与资源 | 暂留作参考，归档前不要直接删除 |
| `_backup/` | 历史压缩备份 | 确认可恢复后另行归档，不再积累新的版本副本 |
| `_compat_check/` | 历史兼容性检查图片、参数和日志 | 保留必要结论与代表性结果，其余逐步清理 |
| [AGENTS.md](AGENTS.md) | AI 工具的项目协作说明 | 调整协作约定时同步维护 |

仓库根目录用于说明整个项目；各模块的具体操作以模块内 README 为准。新增功能优先在现有模块中修改，避免复制一整套工程再命名为“新版”“最终版”。

## 环境准备

`FruitTreesBuild` 当前启动代码要求 Windows，或能调用 Windows 程序的 WSL。普通 Linux、macOS 和 GitHub Codespaces 暂不能直接运行这套 Windows 建树启动流程；可以用来阅读、编辑代码和完成 Git 协作。

| 环境 | 当前要求 |
| --- | --- |
| Python | 3.9+，用于运行外部启动脚本 |
| Blender | 当前建树代码检查 5.2.x；不要直接替换为其他版本 |
| PowerShell | Windows PowerShell 7，即 `pwsh.exe` |

Blender 使用自己的 Python 环境，不需要给外部 Python 安装 `bpy`。克隆仓库不会自动获得 Blender 和 PowerShell；`.runtime/` 属于本地运行环境，不随 Git 提交。

三份共享配置的 `blenderPath` 默认是 `null`，三个 Python 入口共用本机探测：PATH、Windows 安装记录、常见安装目录，最后检查可选的 `.runtime/blender*/blender.exe`。找到后检查 Blender 5.2.x，并显示路径、版本和来源。WSL 使用 Windows Blender，不支持用 Linux Blender 替代。

自定义安装位置可在 `FruitTreesBuild/.runtime/local.json` 写入：
```json
{"blenderPath": "D:/Blender/blender.exe"}
```
这里只是本机配置，不需要复制 Blender；该文件已被 Git 忽略。路径相对于 `FruitTreesBuild/`，也支持绝对路径，建议使用 `/`。
优先级为 `--blender` → 环境变量 `FRUITTREES_BLENDER` → 本机配置 → 共享配置的非空 `blenderPath` → 自动探测。明确指定的路径不存在或版本不符会报错，不会改用另一个程序；本机配置损坏也会报错。团队共享配置保持 `null`。

PowerShell 沿用已有查找逻辑：可选 `.runtime/powershell/pwsh.exe`、PATH 和已有备用位置。无需每个项目再安装一套；PyCharm 应能访问 `pwsh.exe`。`.runtime/user/` 只保存项目隔离设置，和可选程序、本机配置都不随 Git 提交。自动探测不安装软件、不缓存、不扫描整盘。

## 建树与素材交付

先进入工作目录：

```bash
cd FruitTreesBuild
```

### 1. 修改配置并生成模型

| 工作 | 修改配置 | 运行命令 |
| --- | --- | --- |
| 生成苹果树 | `configs/apple_tree.json` | `python generate_apple_tree.py` |
| 生成橙子树 | `configs/orange_tree.json` | `python generate_orange_tree.py` |

日常修改树高、叶片数、果实数和随机种子等参数，优先编辑配置文件。苹果入口保持 `fruit=apple`，橙子入口保持 `fruit=orange`；运行时不需要额外填写命令行参数。

生成结果保存在 `generated/` 中，苹果和橙子分别编号。以控制台输出的实际目录为准，不要删除用于连续编号的 `generated/.asset-numbering.json`。

### 2. 在 Blender 中检查并保存

打开生成目录中的 `asset.blend`，检查树形、材质、叶果连接和穿模情况，调整后保存。具体编辑约束见 [FruitTreesBuild 使用说明](FruitTreesBuild/README.md)。

正式审核和交付使用 `asset.blend`。`scene.blend` 是构建时的调试场景，不会自动同步后续人工修改。

### 3. 导出素材元数据

编辑 `configs/export_metadata.json`，将 `assetDir` 改成实际审核过的素材目录，例如：

```json
{
  "assetDir": "generated/apple_tree_001"
}
```

上面只展示需要修改的字段，不要用它覆盖整份配置。确认目标正确、模型已保存后运行：

```bash
python generate_metadata.py
```

最终交付同一素材目录下的 **`asset.blend` 与 `asset_metadata.json`**。后续再次修改或重存模型，需要重新导出元数据，保证两者匹配。`metadata.json` 是构建记录，不能代替素材级的 `asset_metadata.json`。

字段定义见 [素材元数据说明](FruitTreesBuild/docs/asset_metadata.md)。

## 协作流程

当前沿用 `main`、`develop` 和功能分支的协作方式：

| 分支 | 用途 |
| --- | --- |
| `main` | 保存经过团队确认的版本 |
| `develop` | 汇总正在开发和验证的改动 |
| `feature/功能名`、`fix/问题名`、`chore/整理事项` | 每次任务的独立工作分支 |

开始任务前，先保存本地工作并更新 `develop`，再从它创建自己的分支。完成后提交 Pull Request（PR，合并请求）到 `develop`，说明改了什么、为什么改，以及做过哪些检查。阶段性验证完成后，再将 `develop` 合入 `main`。

同一项改动只开发一次，通过合并传递到其他分支。尽量避免直接修改 `main`；如有必要的主线修复，应及时合并回 `develop`。多人修改同一文件前先沟通分工。

提交前检查改动列表，避免把本机路径、缓存、运行环境、批量生成结果或无关文件一起提交。功能修改和大规模目录整理尽量分开，便于检查和回退。

## 文件保留与测试

源码、工作配置、必要的模型和贴图、文档及测试需要版本管理。`vendor/` 中的部分旧代码仍被当前程序读取，不能仅凭文件名旧就删除；来源和授权说明见 [THIRD_PARTY_NOTICES.md](FruitTreesBuild/docs/THIRD_PARTY_NOTICES.md)。

本地运行环境、Python 缓存、个人 IDE 状态和生成产物按根目录 `.gitignore` 管理。忽略规则不会自动移除已跟踪文件，历史内容需要在确认归档后单独整理。

`generated/` 中经过人工调整的模型并非随时可以重建，必须另外备份和交付。共享素材要同时保留对应元数据，不要只传模型或只传 JSON。

在配置好的支持环境中，从 `FruitTreesBuild/` 运行现有回归测试：

```bash
python -B -m unittest discover -s tests -v
```

测试通过不等于模型已通过外观审核。涉及建树算法、材质或素材导出的修改，还需要实际运行 Blender，并记录环境、配置和检查结果。仓库中的历史验证报告仅说明当时的检查结果，不能代替当前提交的验证。

## 当前待完善

- 补齐运行环境的可复现安装步骤和新成员上手验证。
- 完善独立插件安装包的获取或打包流程；其 README 引用的 `release/SCA_Tree_Generator_0.2.17_Blender_5.2.1.zip` 当前未随仓库提供。
- 验证新工程可以独立运行后，归档旧框架、历史备份和检查产物。

当前工程主要提供单株果树的外观模型及元数据，尚不包含完整果园场景、导航、智能体训练或物理碰撞系统。

