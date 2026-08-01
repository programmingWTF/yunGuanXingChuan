# GitHub 协作入门指南 — 从零开始

> 写给**不太熟悉 Git/GitHub** 的团队成员。跟着做一遍就会了，遇到问题先翻到最后的 [常见问题排查](#常见问题排查)。
>
> 本指南针对「云观星传」项目的**私有仓库**定制。仓库地址：`https://github.com/programmingWTF/yunGuanXingChuan`

---

## 目录

- [第零步：先知道三件重要的事](#第零步先知道三件重要的事)
- [第一步：安装 Git](#第一步安装-git)
- [第二步：配置身份](#第二步配置身份)
- [第三步：克隆仓库到本地](#第三步克隆仓库到本地)
- [第四步：创建你的分支（最重要！）](#第四步创建你的分支最重要)
- [第五步：改代码 + 提交](#第五步改代码--提交)
- [第六步：推送到 GitHub](#第六步推送到-github)
- [第七步：创建 Pull Request（PR）](#第七步创建-pull-requestpr)
- [第八步：Review 与合并](#第八步review-与合并)
- [日常工作的完整流程（速查）](#日常工作的完整流程速查)
- [不想敲命令？用图形界面](#不想敲命令用图形界面)
- [Issue 协作技巧](#issue-协作技巧)
- [常见问题排查](#常见问题排查)
- [推荐工具](#推荐工具)
- [小贴士](#小贴士)

---

## 第零步：先知道三件重要的事

### ① 这是一个私有仓库

我们的仓库是 **Private（私有）** 的，不是任何人都能看到的公开仓库。这意味着：

- 只有**被邀请为协作者**的成员才能访问、修改
- **首次使用**：联系组长，把你的 GitHub 用户名告诉组长，由组长在 GitHub 上邀请你
- 你 clone / push 时需要用**自己的 GitHub 账号**登录

### ② 这是比赛项目，安全红线不能碰

「云观星传」是要参加挑战杯的比赛项目，代码和文档**不要外传**，同时：

| ❌ 绝对不要做 | 为什么 |
|--------------|--------|
| 把 `.env` 文件提交到仓库 | 里面有 API Key，一旦泄露等于把模型调用额度送给别人 |
| 在 Issue / PR / 群里贴 API Key | 同上 |
| 把项目代码打包发给仓库外的人 | 比赛公平性 + 版权 |
| 在公开平台晒项目截图 | 可能泄露尚未公开的创意 |

> 代码层面的保护已经做好了：`.gitignore` 会自动忽略 `.env`、`node_modules` 等敏感/大文件。**你需要做的是：提交前看一眼 `git status`，确认没有把不该提交的文件加进去。**

### ③ 我们的主分支叫 `main`

所有协作都围绕 **`main`** 分支进行：从它拉取最新代码、从它开自己的分支、最后合并回它。这是团队协作的唯一主干。

---

## 第一步：安装 Git

### Windows

1. 下载：https://git-scm.com/download/win
2. 双击安装，一路点「下一步」，**全部保持默认**即可
3. 安装完成后，在桌面或任意文件夹里点**右键**，选择 **"Open Git Bash Here"**，会打开一个黑窗口
4. 在窗口里输入：
   ```bash
   git --version
   ```
   看到类似 `git version 2.xx.x.windows.x` 就说明安装成功了

> 💡 Git 自带三种终端：Git Bash、Git CMD、Git GUI。**推荐用 Git Bash**（和 Mac/Linux 的命令一样，教程里的命令都能直接用）。

### Mac

```bash
brew install git
```
或下载：https://git-scm.com/download/mac

### Linux（Ubuntu/Debian）

```bash
sudo apt install git
```

---

## 第二步：配置身份

Git 每次提交都会记录"是谁改的"，所以要先告诉它你的名字和邮箱。

打开 Git Bash（或终端），输入下面两行，**把内容换成你自己的**：

```bash
git config --global user.name "你的姓名"
git config --global user.email "你的GitHub注册邮箱"
```

示例：
```bash
git config --global user.name "张三"
git config --global user.email "zhangsan@nuaa.edu.cn"
```

> ⚠️ 邮箱**必须**用注册 GitHub 用的那个邮箱，否则 GitHub 无法把你的提交和账号关联起来（绿色小方块不亮）。

---

## 第三步：克隆仓库到本地

1. **确认你已被邀请为协作者**（还没邀请？回到第零步 ①）
2. 打开 Git Bash，先进入你想放项目的目录，比如放桌面：
   ```bash
   cd ~/Desktop
   ```
   > 也可以先 `cd` 到你习惯的目录，比如 `cd D:/Code`（Windows 下斜杠用 `/` 或 `\` 都行）
3. 克隆仓库：
   ```bash
   git clone https://github.com/programmingWTF/yunGuanXingChuan.git
   cd yunGuanXingChuan
   ```
4. 因为是私有仓库，第一次操作会弹出窗口要求**登录你的 GitHub 账号**（网页登录一次即可，之后会用 Windows 凭据管理器记住）

现在你本地就有一份完整代码了。

---

## 第四步：创建你的分支（最重要！）

### 为什么永远不要在 `main` 上直接改？

`main` 是所有代码的"最终合流处"，是大家共享的地盘。如果直接在 `main` 上改，你的改动会**直接进主分支**，很容易和别人的工作撞车。

**正确姿势：每次工作都开一个自己的分支，做完再合并回去。**

### 开始前的标准动作（三连）

```bash
git checkout main        # ① 先切回主分支
git pull origin main     # ② 拉取最新代码（必须！）
git checkout -b 你的分支名  # ③ 创建并切换到新分支
```

> [!CAUTION]
> **② 这一条（`git pull origin main`）绝对不能省！**
>
> 如果你跳过 pull、直接在自己电脑的旧代码上改，等你 push 的时候，会把别人已经合并进去的新代码覆盖掉，导致**队友的工作白做**。这是团队协作里最常见、也最严重的事故。
>
> 每次开工前记住三句话：**先切回 → 先拉最新 → 再开分支**。缺一不可。

### 分支命名规则（按类型）

我们人不多，按"这次要做什么事"来命名分支，用**类型前缀**区分：

| 前缀 | 什么时候用 | 示例 |
|------|-----------|------|
| `feat/` | 加新功能 | `feat/kg-partition`（知识图谱分区浏览） |
| `fix/`  | 修 bug | `fix/parliament-display`（修复辩论显示） |
| `docs/` | 改文档 | `docs/github-guide` |
| `data/` | 改数据/语料/受众画像 | `data/media-france` |
| `style/` | 前端样式、视觉、图表 | `style/starfield-bg` |
| `refactor/` | 重构代码（不改行为） | `refactor/pipeline` |

> **一个分支只做一件事**。不要在一个分支里既改文档又加功能——Review 的人会疯掉的。

---

## 第五步：改代码 + 提交

### 5.1 改代码

用你喜欢的编辑器打开项目文件夹（推荐 VS Code），修改文件。

### 5.2 查看改了什么

```bash
git status          # 看改了哪些文件（红色 = 已修改）
git diff            # 看每个文件具体改了什么内容
```

### 5.3 暂存改动（stage）

Git 提交分两步：先把要提交的文件"挑进篮子"，再一次性提交。这个"挑进篮子"就是暂存。

```bash
git add 具体文件路径    # 只添加某个文件，如 git add src/pipeline.py
git add .             # 添加所有改动（⚠️ 小心：可能把不该提交的也加进来）
git add src/ api/     # 添加某些目录
```

> [!TIP]
> 提交前务必跑一次 `git status`，**检查暂存区（绿色区域）里有没有 `.env`、`node_modules`、临时文件**。有的话用 `git restore --staged 文件` 把它移出来。

### 5.4 提交（commit）

```bash
git commit -m "<type>(<scope>): <简短描述>"
```

**格式**（完整规范见 [CONTRIBUTING.md](../CONTRIBUTING.md)）：

```
<类型>(<模块>): <一句话说清楚做了什么>
```

**类型**：`feat`（新功能）、`fix`（修 bug）、`docs`（文档）、`data`（数据）、`style`（样式）、`refactor`（重构）、`chore`（杂项）

**模块（scope）**：`agents`（智能体）、`parliament`（议会辩论）、`pipeline`（流程编排）、`api`（后端接口）、`frontend`（前端）、`kg`（知识图谱）、`data`（数据）、`docs`（文档）、`scripts`（脚本）

**示例**：
```bash
git commit -m "feat(kg): 知识图谱增加连通分量分区浏览"
git commit -m "fix(parliament): 修复辩论发言全文换行显示"
git commit -m "data(media): 添加法国媒体嫦娥六号报道语料"
git commit -m "docs(collab): 更新团队协作文档"
```

> [!TIP]
> - **勤提交**：改完一个完整的小改动就提交一次，不要攒几百行再提交
> - 提交信息写错了：`git commit --amend -m "新的正确信息"` 修改上一次提交

---

## 第六步：推送到 GitHub

```bash
git push origin 你的分支名
```

示例：
```bash
git push origin feat/kg-partition
```

**第一次 push 某个新分支**时，Git 可能会提示：
```
fatal: The current branch has no upstream branch.
To push the current branch and set the remote tracking branch, use

    git push --set-upstream origin feat/kg-partition
```

别慌，这**不是报错**，只是 Git 想让你明确"这个新分支推到远程叫什么名字"。把提示里的命令复制执行即可：
```bash
git push --set-upstream origin feat/kg-partition
```

之后对这个分支就只需要 `git push` 了。

---

## 第七步：创建 Pull Request（PR）

PR（Pull Request，拉取请求）是 Git 协作的核心：**把你分支上的改动"申请"合并进 `main`，让队友先检查一遍**。

1. 打开仓库网页：https://github.com/programmingWTF/yunGuanXingChuan
2. 刚 push 完后，页面顶部会出现黄色提示条 **"feat/kg-partition had recent pushes"**，点击 **Compare & pull request**
3. 如果没有提示条，点顶部 **Pull requests** 标签 → 右侧绿色按钮 **New pull request**
4. 确认合并方向（非常重要）：
   - **base**: `main`（代码合并到哪）
   - **compare**: 你的分支（从哪来）
5. 填写标题和描述：
   - 标题遵循提交信息格式：`<type>(<scope>): <描述>`
   - 描述里说清楚：做了什么、为什么这样做、怎么测试的
   - **重要**：如果这个改动在解决某个 Issue，在描述第一行写 `Closes #编号`（如 `Closes #58`），合并后 GitHub 会自动关闭对应 Issue
6. 点 **Create pull request**
7. 在群里 @ 队友（至少一位）帮忙 Review

> 💡 **PR 不是"提交作业"，是"请队友把关"**。发出去不丢人，合并前发现问题是好事；合并后发现 bug 才麻烦。

---

## 第八步：Review 与合并

- 等**至少一个人**在你的 PR 页面点 **Approve**
- 如果 Review 的人提了修改意见：
  1. 在本地改代码
  2. `git add .` → `git commit -m "fix(<scope>): 按 review 意见修改..."` → `git push`
  3. **PR 会自动更新**，Reviewer 能立刻看到新改动
- 全部通过后，点绿色的 **Squash and merge** 合并进 `main`（仓库已开启保护 + Squash 合并，PR 会压缩成**一条**提交，`main` 历史干净）
- 分支会在合并后**自动删除**（仓库已开启"合并后删除分支"），无需手动清理

> [!TIP]
> 合并进 `main` 的代码，就是"最终成果"。下次别人 `git pull` 就能拿到你的代码。所以合并前一定要确保它**能跑**。

---

## 日常工作的完整流程（速查）

以后每次改代码，都走这个流程：

```bash
# 1. 切到 main 并拉最新（三连第一步）
git checkout main
git pull origin main

# 2. 创建新分支（三连第二步）
git checkout -b feat/xxx

# 3. 改代码……

# 4. 查看改了什么
git status
git diff

# 5. 暂存 + 提交（先 git status 确认没夹带敏感文件）
git add .
git commit -m "feat(parliament): xxx"

# 6. 推送
git push origin feat/xxx

# 7. 去 GitHub 网页创建 PR → 等 Review → 合并
```

把这张图贴在脑子里：

```
main ──┬── feat/xxx ── 改代码 ── commit ── push ──> PR ── Review ──> 合并回 main
         └── fix/yyy ── 改代码 ── commit ── push ──> PR ── Review ──> 合并回 main
```

---

## 不想敲命令？用图形界面

上面所有操作都有图形界面替代。两种最常用的：

### 方法 A：VS Code 自带 Git 面板（推荐）

VS Code 左侧有一个「源代码管理」（Source Control）图标，像个分支的图形：

| 你想要的 | 怎么点 |
|---------|--------|
| 看改了哪些文件 | 点左侧源代码管理图标，红色列表 = 已修改 |
| 暂存 | 文件右边的 `+` 号 |
| 提交 | 顶部输入框写提交信息，点「提交」✓ |
| 推送 | 点「更改」右上角的 `...` → 「推送」 |
| 创建分支 | 点左下角当前分支名 → 输入新分支名 → 回车 |
| 拉取最新 | 点 `...` → 「拉取」 |
| 解决冲突 | 冲突文件会标红，点开手动改 |

VS Code 还推荐装 **GitLens** 插件，能可视化每一行代码是谁写的、什么时候改的。

### 方法 B：GitHub Desktop（纯图形）

完全不用敲命令，适合零基础：

1. 下载安装：https://desktop.github.com/
2. 登录你的 GitHub 账号
3. File → Clone repository → 找到 yunGuanXingChuan → 克隆
4. 界面上会显示所有改动，勾选文件、写提交信息、点 Commit
5. 点 **Push origin** 推送
6. 点 **Create Pull Request** 直接跳转到网页开 PR

> 图形界面方便，但遇到复杂情况（冲突、历史修改）还是命令行更稳。**建议两条腿走路：日常用图形界面，出问题用命令行排查。**

---

## Issue 协作技巧

Issue 就是"任务清单"。所有要做的功能、要修的 bug，都应该先在 Issue 里登记，再动手写代码。

### 怎么知道一个 Issue 有没有人在做？

开始写代码之前，先看这个 Issue 是否已被认领：

1. 打开 Issue 页面，看右侧 **Assignees**（指派）一栏
   - 有头像 → **已经有人在做了**，换个 Issue，或去评论区问还需不需要帮忙
   - 空着 → 还没人做，可以认领
2. 翻一下评论区，看有没有人留言「我来做这个」
3. 看时间线里有没有 "linked a pull request" → 说明已经有 PR 在修了

### 怎么认领一个 Issue？

1. 在 Issues 列表里找一个没人做的（没有 Assignee 的）
2. 打开它，在评论区发一句「我来做这个」
3. 点右侧 **Assignees** → 点自己的头像，把自己设上去
4. 开始写代码！

> [!CAUTION]
> **一定要先 Assign 再动手。** 两个人同时修同一个 bug → 其中一个人白干。花 10 秒点个 Assign，省几十分钟。

### 怎么在 PR 里关联 Issue？

创建 PR 时，在描述里写一行：

```markdown
Closes #58
```

就这一行。合并 PR 后，GitHub 会自动把 Issue #58 关掉。

- 等价写法：`Fixes #58`、`Resolves #58`
- 多个 Issue：`Closes #58, closes #59`
- **建议放在 PR 描述第一行**，这样 Reviewer 一进来就能看到关联的任务

### 提 Issue 时要注意什么？

提 Issue 时，GitHub 会自动弹出我们配好的模板（Bug 报告 / 功能请求），**按模板填**。模板会引导你说清楚：现象、复现步骤、期望行为、涉及模块。填得越清楚，队友越能快速帮你。

---

## 常见问题排查

### Q: 提交时提示 "Please tell me who you are"
说明没配置身份。回到[第二步](#第二步配置身份)执行那两行配置命令。

### Q: clone 或 push 时提示 "Permission denied" / 403
你的 GitHub 账号没被加为仓库协作者，或者登录的不是受邀的账号。联系组长检查成员列表。

### Q: push 时提示 "failed to push, the remote contains work that you do not have locally"
别人在你之前 push 了新代码。先拉取再推送：
```bash
git pull origin main
git push origin 你的分支名
```

### Q: 合并时有冲突（conflict）
**别慌**。冲突 = 你和别人改了同一个文件的同一行。Git 无法自动决定听谁的，需要你手动裁决。

1. 打开冲突文件，会看到类似这样的标记：
   ```
   <<<<<<< HEAD
   你的代码
   =======
   别人的代码
   >>>>>>> feat/xxx
   ```
2. 手动**删除标记行**，保留最终想要的内容（可能要综合两边）
3. 保存后：
   ```bash
   git add .
   git commit -m "fix(merge): 解决合并冲突"
   git push origin 你的分支名
   ```

> 💡 用 VS Code 打开冲突文件时，界面会提供 "Accept Current / Accept Incoming / Accept Both" 三个按钮，直接点更省事。

### Q: 我不小心在 main 上改了代码
```bash
git stash               # ① 把改动暂存起来
git checkout -b 新分支名  # ② 开新分支
git stash pop           # ③ 把改动恢复到这个新分支
```
然后正常提交即可。

### Q: 提交信息写错了想改
```bash
git commit --amend -m "正确信息"
git push --force-with-lease origin 你的分支名
```
> ⚠️ `--amend` 只能改**还没被合并**的提交，且改完要用 `--force-with-lease`（别用裸 `--force`）。

### Q: 我想放弃本地的所有改动
```bash
git checkout .        # 放弃所有未暂存的修改（已 add 的用 git restore --staged 先撤回）
git clean -fd         # 删除新增的未跟踪文件
```
> ⚠️ 这两个命令**不可恢复**，执行前确认你真的不想要这些改动了。

### Q: 我想把某个文件恢复成 main 上的样子
```bash
git restore 文件名     # 或 git checkout -- 文件名
```

### Q: 怎么撤销最近一次提交
```bash
git reset --soft HEAD~1    # 撤销提交但保留改动（可重新提交）
git reset --hard HEAD~1    # 撤销提交并丢弃改动（⚠️ 慎用）
```

### Q: 直接 push main 被拒绝（"protected branch"）
我们仓库**已经开启 main 保护分支**：任何改动（包括组长的）都必须走 **分支 → PR → 至少一人 Approve** 才能合并，直接 push `main` 会被 GitHub 拒绝。这是仓库的**硬性规则**，不是建议——别尝试绕开它，让流程替你把关。

---

## 推荐工具

| 工具 | 用途 |
|------|------|
| **VS Code** | 推荐编辑器，内置 Git 图形界面（源代码管理面板） |
| **GitHub Desktop** | https://desktop.github.com/ — 纯图形界面，不想碰命令行的首选 |
| **GitLens**（VS Code 插件） | 可视化每行代码的作者、修改历史 |
| **Oh My Zsh / Git 别名** | 进阶：把常用命令缩短，如 `git co` = `git checkout` |

---

## 小贴士

1. **勤提交**：一个完整小改动就提交一次，别攒到天黑
2. **勤 pull**：每天开工先 `git pull origin main`，冲突概率直线下降
3. **一个分支只做一件事**：功能分支别顺手改文档
4. **先 pull 再 push**：push 前先 `git pull origin main`，减少冲突
5. **提交前看 `git status`**：防呆防 `/.env` 进仓库
6. **别 panic**：Git 几乎所有操作都能撤销，别把整个文件夹删了重来
7. **拿不准就问**：宁可多问一句，也别用一个危险命令把仓库搞坏

---

## 附：术语速查

| 术语 | 意思 |
|------|------|
| **仓库（Repository）** | 存放代码和历史的"文件夹"（带 `.git` 的那层） |
| **clone** | 把远程仓库完整复制到本地 |
| **分支（branch）** | 平行的工作线，互不干扰 |
| **checkout** | 切换分支 |
| **pull** | 把远程的更新拉下来 |
| **push** | 把本地提交推上去 |
| **commit** | 一次"存档"，记录改动和作者 |
| **stage / add** | 把改动挑进提交篮子的动作 |
| **merge** | 把一个分支的改动合并进另一个 |
| **PR（Pull Request）** | 申请合并 + 让队友 Review 的载体 |
| **Issue** | 任务 / bug / 建议的登记单 |
| **Review** | 检查别人代码并给意见 |
| **conflict** | 两边改了同一处代码，需人工裁决 |
