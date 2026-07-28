# 行业追踪与市场情绪研究看板

轻量化专业投研风的单页静态看板：采集半导体设备 / CPO / 国产算力 / 存储芯片 / 恒生科技五大赛道过去 24 小时的公开资讯，标准化标注事件属性后可视化呈现。

> 合规声明：本看板仅提供资讯证据的客观整理，不构成任何投资建议。

## 项目结构

```
├── index.html                      # 主页面（内嵌全部 CSS/JS，数据与页面完全分离）
├── data/
│   └── events.json                 # 结构化数据（每日由工作流自动覆盖更新）
├── scripts/
│   ├── generate_data.py            # 数据生成脚本（调用大模型 API 采集并标注资讯）
│   └── requirements.txt            # Python 依赖
├── .github/
│   └── workflows/
│       └── daily-update.yml        # 每日定时更新工作流
└── README.md
```

## 一、从零到一部署（约 10 分钟）

### 1. 创建仓库并上传文件

```bash
git init
git add .
git commit -m "feat: 行业追踪与市场情绪研究看板初始化"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

也可以直接在 GitHub 网页端 **New repository** 后用 **Add file → Upload files** 上传（注意保持目录结构，`.github` 文件夹不能丢）。

### 2. 开启 GitHub Pages

仓库页 → **Settings → Pages** → **Build and deployment**：

- Source 选择 **Deploy from a branch**
- Branch 选择 **main**，目录保持 **/ (root)**，点 Save

约 1 分钟后页面生效，访问地址为：
`https://<你的用户名>.github.io/<仓库名>/`

> 仓库可设为 Private：GitHub Free 账户 Private 仓库默认也能开 Pages（如需私有 Pages 访问控制需 Pro 及以上）；若遇限制，将仓库改为 Public 即可。

### 3. 配置密钥（Secrets / Variables）

仓库页 → **Settings → Secrets and variables → Actions**：

| 类型 | 名称 | 说明 |
|---|---|---|
| Secret | `LLM_API_KEY` | 大模型 API 密钥（必填） |
| Variable | `LLM_BASE_URL` | API 基础地址，可选，默认 `https://api.moonshot.cn/v1`（OpenAI 兼容接口均可） |
| Variable | `LLM_MODEL` | 模型名，可选，默认 `kimi-k2-0905-preview` |

无需配置 GitHub Token：工作流已声明 `permissions: contents: write`，使用内置 `GITHUB_TOKEN` 推送。

### 4. 测试运行

仓库页 → **Actions → Daily Data Update → Run workflow** 手动触发一次。

- 绿色勾：打开 `data/events.json` 确认出现最新提交（提交人为 `github-actions[bot]`），刷新 Pages 页面验证数据更新。
- 红色叉：点进运行记录查看 `生成最新数据` 步骤日志，按下方「常见问题」排查。

## 二、定时任务修改

定时配置位于 `.github/workflows/daily-update.yml`：

```yaml
on:
  schedule:
    - cron: "0 1 * * *"   # UTC 时间；北京时间 09:00 = UTC 01:00
```

- GitHub Actions 的 cron **只支持 UTC**，换算：北京时间 − 8 小时 = UTC。
- 例：改为每天北京时间 08:30 → `cron: "30 0 * * *"`；每天 18:00 → `cron: "0 10 * * *"`。
- 注意：GitHub 定时任务在高负载时段可能延迟数分钟到数十分钟，属官方已知行为。
- 手动触发不受影响，随时可在 Actions 页 **Run workflow**。

## 三、共享链接

部署完成后，看板地址 `https://<你的用户名>.github.io/<仓库名>/` 即为共享链接，任何浏览器可直接打开（Public 仓库）；移动端自适应单栏布局。

## 四、本地预览

- **直接双击 `index.html` 即可打开**：检测到 `file://` 协议时页面会自动切换为内置示例数据渲染（顶部时间窗口会标注「本地预览数据」）。
- 如需预览 `data/events.json` 中的最新真实数据，请用任一静态服务器：

```bash
python -m http.server 8080
# 浏览器打开 http://localhost:8080
```

> 注意：内置示例数据仅作 `file://` 兜底预览，不会随每日工作流更新；线上环境（HTTP）始终读取 `data/events.json`。

## 五、常见问题排查

**1. 页面显示「数据加载失败」**
- 直接双击打开（`file://` 协议）时页面会自动使用内置示例数据；若仍报错，请确认 `index.html` 中包含 `id="embeddedData"` 的内置数据块；
- 通过 HTTP 访问时，打开浏览器 DevTools → Network，确认 `data/events.json` 返回 200 且为合法 JSON（可用 `python -m json.tool data/events.json` 本地校验）；
- Pages 有 CDN 缓存，强制刷新（Ctrl+F5）或等待 1-2 分钟。

**2. 工作流在「生成最新数据」步骤失败**
- 401/403：`LLM_API_KEY` 未配置或已过期，检查 Secrets 名称拼写（必须与 `LLM_API_KEY` 完全一致）；
- 404：`LLM_BASE_URL` / `LLM_MODEL` 与服务商不匹配；
- 输出校验失败：模型未返回合法 JSON 或字段不合规。脚本会自动保留旧数据并触发重试（最多 3 次）；可换用更强模型，或在 `scripts/generate_data.py` 的 `search_news()` 接入实时检索 API 提升输出质量。

**3. 工作流在「提交并推送」步骤失败**
- 确认工作流文件含 `permissions: contents: write`；
- Settings → Actions → General → Workflow permissions 选择 **Read and write permissions**；
- 分支保护规则限制 main 直接推送时，需对 `github-actions[bot]` 放行。

**4. 定时任务没有按时执行**
- GitHub 定时任务在 UTC 整点前后高负载，延迟属正常现象；
- 仓库 60 天无活动时 GitHub 会自动暂停定时工作流，届时到 Actions 页点 **Enable workflow** 恢复。

**5. 数据每天没变**
- 脚本校验失败时会保留旧文件并失败退出，查看 Actions 日志；
- 确认工作流最近一次运行成功（绿色），且提交记录中有 `chore(data)` 前缀的自动提交。
