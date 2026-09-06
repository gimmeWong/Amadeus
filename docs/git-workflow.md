# Git 分支工作流

本仓库同时维护原作者仓库和个人 fork。为避免把未完成的功能混入主线，统一使用下面的分支职责：

| 分支 | 作用 | 是否直接开发 |
| --- | --- | --- |
| `upstream/main` | 原作者仓库的最新代码，只读参考 | 否 |
| 本地 `main` | 同步上游的干净基线 | 否 |
| `origin/main` | 个人 fork 的主分支，与本地 `main` 同步 | 否 |
| `personal/main` | 个人完整、可运行、经过测试的产品主线 | 仅通过合并进入 |
| `feature/*` | 新功能 | 是 |
| `fix/*` | 缺陷修复 | 是 |

## 安装仓库检查

首次克隆后，在仓库根目录运行：

```powershell
.\scripts\setup_git_workflow.ps1
```

它会将当前仓库的 `core.hooksPath` 设置为 `.githooks`。设置保存在本地 `.git/config`，不会修改全局 Git，也不会影响其他仓库。

## 同步主线

在没有未提交改动时运行：

```powershell
.\scripts\sync_main.ps1
```

脚本执行以下等价操作：

```text
git fetch upstream --prune
git switch main
git merge --ff-only upstream/main
git push origin main
```

如果本地 `main` 有提交、存在未提交改动，或上游无法快进合并，脚本会停止并要求人工处理，不会自动重写历史。

## 开始一个工作项

主线同步后运行：

```powershell
.\scripts\new_work_branch.ps1 -Name chat-history -Kind feature
```

这会从最新的本地 `main` 创建并切换到 `feature/chat-history`。修复类工作使用：

```powershell
.\scripts\new_work_branch.ps1 -Name wallpaper-reconnect -Kind fix
```

开发期间不要在 `main` 或 `personal/main` 上直接开发。一个独立功能或问题使用一个独立分支；完成后再推送到个人 fork：

```powershell
git push -u origin feature/chat-history
```

## 维护个人完整主线

`personal/main` 是个人 fork 中叠加了多个已选择、已验证功能的完整产品版本。它不是上游同步分支，也不是日常开发分支；只把已经完成测试的 `feature/*` 或 `fix/*` 合并进去。

首次创建个人主线：

```powershell
git switch main
git switch -c personal/main
git push -u origin personal/main
```

将经过验证的工作项合并到个人主线：

```powershell
git switch personal/main
git merge --no-ff feature/chat-history
# 运行相关测试并确认通过
git push origin personal/main
```

工作项完成后，使用晋级脚本完成完整顺序。脚本会先推送当前 `feature/*` 或 `fix/*` 到 `origin`，再抓取 `upstream`，更新并推送 `main`，把最新 `main` 和指定的工作分支合并到 `personal/main`，运行 Electron 测试，只有测试成功才推送 `personal/main`：

```powershell
git switch feature/chat-history
.\scripts\promote_personal_main.ps1
```

也可以显式指定工作分支：

```powershell
.\scripts\promote_personal_main.ps1 -WorkBranch fix/wallpaper-reconnect
```

脚本默认要求 `electron` 测试通过；测试失败或合并冲突时会停止，不推送 `personal/main`。`pre-push` 会阻止绕过脚本手工推送 `personal/main`。`-SkipOriginMainPush` 只在你明确不想更新 fork 的 `main` 时使用，仍会先把本地 `main` 快进到 `upstream/main`。

`main` 始终只跟踪上游的干净基线；`personal/main` 才是包含个人功能的完整版本。上游更新会先进入 `main`，不会自动改写或覆盖 `personal/main`。需要更新个人主线时，先把工作项基于最新 `main` 验证，再按需合并进入 `personal/main`。

## 同步开发中的分支

上游有新提交时，先更新主线，再将工作分支变基到主线：

```powershell
.\scripts\sync_main.ps1
git switch feature/chat-history
git rebase main
git push --force-with-lease origin feature/chat-history
```

`--force-with-lease` 只用于自己 fork 上已经推送过、且经过变基的工作分支；不要对 `main` 使用强制推送。

## 保护边界

- `pre-commit` 会阻止直接在 `main` 和 `personal/main` 上提交；`personal/main` 允许经过测试的合并提交。仅在确认要制作特殊维护提交时，临时设置 `$env:AMADEUS_ALLOW_MAIN_COMMIT = '1'`。
- `pre-push` 会阻止向 `upstream` 推送，避免误操作原作者仓库。
- hooks 只负责提醒和阻止明显错误；`promote_personal_main.ps1` 负责个人主线晋级，主线同步、分支命名和审查仍以本文件为准。普通 feature/fix 推送不会自动合并到 `personal/main`，避免未测试的 WIP 改动污染完整主线。

## 查看状态

```powershell
git status --short --branch
git log --oneline --decorate --graph --all -20
git branch -vv
```
