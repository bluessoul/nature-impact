English version: [README.en.md](README.en.md)

# Nature Impact — 学术影响力与成果治理技能包 (nature-impact)

[![Install](https://img.shields.io/badge/install-Codex%20%7C%20Claude%20Code%20%7C%20Antigravity%20%7C%20OpenClaw%20%7C%20OpenCode%20%7C%20Hermes-111827)](#多平台接入与安装指南)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Nature Skills Family](https://img.shields.io/badge/ecosystem-Nature%20Skills-green.svg)](https://github.com/Yuan1z0825/nature-skills)

> **`nature-impact`**（原 `scholar-impact-scraper`）是 **Nature Skills 学术工具生态** 中的学者学术影响力评估、期刊分区评价与代表作成果治理核心技能包。

## 它解决什么问题

科研人员、研究助理、学术带头人（PI）和科研管理人员经常需要反复整理同一批信息：
- 某位学者在 **Google Scholar** 的论文、引用量、h-index、i10-index；
- **Web of Science (WoS)** 的核心合集引用与他引数据；
- **ORCID** 官方认证成果列表；
- **Clarivate JCR** 期刊学科类别、影响因子（IF）、四分位分区（Q1-Q4）及排名；
- **中科院期刊分区（CAS）** 升级版大类/小类分区与 Top 期刊判定；
- 简历（CV）/申报表中论文成果的作者位次、第一作者/通讯作者判定、DOI 与卷期页码补全，以及按 **GB/T 7714-2025** 等最新国标导出参考文献。

这些信息分散在不同平台，手工复制粘贴耗时且极易出错。**`nature-impact`** 把这些繁琐的数据工作封装为标准的 Agent 技能与命令行自动化流程，无缝适配 **Codex、Claude Code、Antigravity、OpenClaw、OpenCode、Hermes** 等主流 Coding Agent 平台。

本项目不会绕过任何平台访问控制。需要账号或机构订阅的功能，仍然要求你使用自己有权访问的账号或本地凭据。

## 典型使用场景

- **简历/模板一键导入与消歧**：用户直接提供 `docx/pdf/txt/md` 简历、单位求职/申请模板，或仅提供“姓名+单位”；`scholar_intake.py` 自动提取学者画像、论文线索和填报要求，并智能识别作者加粗、下划线和通讯作者标记。
- **基金申请与职称材料整理**：批量整理学者论文、引用、作者顺序、通讯作者线索、DOI、卷期页码，并按 APA、MLA、Chicago、Harvard、LaTeX/BibTeX、AMA、GB/T 7714 或最新的 **GB/T 7714-2025** 导出参考文献。
- **学者影响力全景扫描**：快速汇总 Google Scholar 与 Web of Science 引用指标，辅助评估候选人、合作者或团队科研产出。
- **论文清单元数据高精度补全**：结合 Google Scholar 详情页、OpenAlex API 与 Crossref 补全 DOI、完整作者列表、通讯作者、期刊/会议、卷期页码和出版社。
- **期刊分区与影响因子核查**：查询 JCR 实时/本地分区及用户本地中科院分区数据，支持投稿选刊与成果归档。
- **与 Nature-Skills 生态联动**：产出的成果列表与影响力数据可直接对接 `nature-writing`、`nature-citation` 和 `nature-paper2ppt`，实现从成果治理到顶刊写作与答辩 PPT 生成的完整闭环。

## 最近更新

### 2026-06-21：简历和模板一键导入

- 新增 `scholar_intake.py`：用户可以直接丢入简历、单位申请模板，或只输入姓名+单位，工具会自动识别该找谁、需要整理什么信息。
- 自动识别姓名、单位、邮箱、ORCID、Google Scholar ID、论文列表和模板里的填报要求，并生成一份用户可读的整理结果。
- Word 简历会尝试识别论文作者中的加粗、下划线和星号标记，帮助判断目标作者、第一作者或通讯作者；PDF 会提醒用户格式识别不可靠，建议提供 Word 文件或补充作者说明。
- 如果信息足够明确，工具会继续调用现有 Scholar/ORCID/JCR 功能补全数据；如果遇到同名学者或证据不足，会先提醒用户确认，避免整理错人。

### 2026-06：论文元数据、引用格式和分区查询增强

- 新增 `gbt2025` 参考文献格式，用于 GB/T 7714-2025。该标准已发布，实施日期为 2026-07-01；旧的 `gbt` 输出仍保留，便于兼容既有材料。
- `gbt2025` 会在 DOI 可用时把期刊/会议文献标为 `[J/OL]` 或 `[C/OL]`，并用 `DOI: 10.xxxx/...` 形式输出 DOI。
- 参考文献交互菜单包含 APA、MLA、Chicago、Harvard、LaTeX/BibTeX、AMA/Numeric、GB/T 7714、GB/T 7714-2025 和 All。
- 默认 Scholar 抓取流程优先使用 Google Scholar 详情页 DOI，再用 OpenAlex 补 DOI、作者、通讯作者、卷期页码、来源和出版社，最后才对仍缺 DOI 的记录使用 Crossref。
- 用户仍可用 `--no-fetch-doi --no-openalex-enrich --no-fetch-corresponding` 关闭增强，做纯 Google Scholar 快速抓取。

## 多平台接入与安装指南

`nature-impact` 遵循标准的 Agent Skill 规范，可无缝接入各种 AI 编码助手与智能体环境：

### 1. Codex 接入

- **全局/项目技能安装**：
  将本仓库克隆或复制到 Codex 技能目录：
  ```bash
  # Windows PowerShell
  git clone https://github.com/bluessoul/nature-impact.git "$HOME\.codex\skills\nature-impact"

  # macOS / Linux
  git clone https://github.com/bluessoul/nature-impact.git ~/.codex/skills/nature-impact
  ```
  或者如果已配置 `skills` CLI：
  ```bash
  npx skills add bluessoul/nature-impact --global --agent codex --skill nature-impact --yes --copy
  ```
- **使用体验**：在 Codex 中直接输入自然语言，例如：
  > “从简历 `cv.docx` 中提取成果并整理近 5 年发表记录，导出 GB/T 7714-2025 格式”
  > “查询论文《Attention Is All You Need》作者在 Google Scholar 的引用与 h-index”

---

### 2. Claude Code 接入

Claude Code 支持通过 **Subagent** 或 **Slash Command** 封装调用本技能：

- **方式 A：Subagent Wrapper（推荐）**
  创建 `~/.claude/agents/nature-impact.md`：
  ```markdown
  ---
  name: nature-impact
  description: 学术影响力评估、Google Scholar/WoS 引用抓取、JCR 分区与成果简历治理
  ---
  你是一个学术数据专家。请严格按照项目内的 `SKILL.md` 和 `AGENTS.md` 执行学者成果与影响力分析。
  执行前先确认年份范围与学者消歧信息，并在本地生成 CSV 和格式化引用。
  ```
  在 Claude Code 中直接呼叫：`使用 nature-impact 子代理帮我整理学者影响力数据`。

- **方式 B：Slash Command 快捷指令**
  创建 `~/.claude/commands/nature-impact.md`：
  ```markdown
  请读取当前工作区或 `~/.codex/skills/nature-impact/SKILL.md`，执行学术成果盘点或 JCR 分区查询任务。
  ```
  在终端中直接输入 `/nature-impact` 触发。

- **方式 C：工作区原生运行**
  直接在包含本项目的目录中运行 `claude`，Claude Code 会自动加载 [`CLAUDE.md`](CLAUDE.md) 和 [`SKILL.md`](SKILL.md)。

---

### 3. Antigravity (AGY) 接入

- **作为独立技能或 Nature-Skills 插件集成**：
  - 复制到 Antigravity 插件目录：
    `~/.gemini/config/plugins/nature-skills/skills/nature-impact/`
  - 或放置在 Antigravity 自定义技能目录：
    `~/.gemini/antigravity/builtin/skills/nature-impact/`
- **使用体验**：Antigravity Agent 会自动索引 `SKILL.md`，并在用户询问“学术影响力、WoS 他引、H 指数、JCR 分区、中科院分区、简历成果提取”时自动触发调用。

---

### 4. OpenClaw / QClaw 接入

- 放置在 `~/.openclaw/skills/nature-impact/`。
- 本仓库已在 `SKILL.md` 中声明 `metadata.openclaw` 所需的环境变量（`ORCID_CLIENT_ID`、`CLARIVATE_EMAIL` 等），OpenClaw 会自动引导配置本地环境变量并按沙箱安全策略执行。

---

### 5. OpenCode 接入

- 将本仓库放置于 `~/.opencode/skills/nature-impact/`。
- 在 OpenCode 会话中直接通过指令或 `@nature-impact` 呼叫学者分析与期刊查询工作流。

---

### 6. Hermes Agent 接入

- 放置于 `~/.hermes/skills/nature-impact/`。
- Hermes Agent 会自动识别并加载路由协议，支持在自动化 Research 流水线中作为数据初筛与分区核查节点。

---

## 运行环境依赖安装

无论使用哪个平台，底层均需要 Python 与 Node.js 基础运行环境：

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
npm install
```

macOS / Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
npm install
```

## 配置本地账号和凭据

复制环境变量模板：

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

然后只在本地 `.env` 中填写你需要的功能对应的值：

```env
ORCID_CLIENT_ID=APP-XXXXXXXXXXXXXXXX
ORCID_CLIENT_SECRET=00000000-0000-0000-0000-000000000000
TARGET_ORCID_ID=0000-0002-1825-0097
OUTPUT_CSV=orcid_publications.csv

CLARIVATE_EMAIL=your_email@institution.edu
CLARIVATE_PASSWORD=your_password

OPENALEX_API_KEY=your_optional_openalex_api_key
```

建议优先使用 `.env` 或系统环境变量。`config.json` 只适合本地临时使用，已经被 `.gitignore` 忽略，不能发布。

## 首次运行：保存浏览器登录状态

如果你要使用 Web of Science 或 Clarivate/JCR 的实时查询，建议第一次先通过登录助手保存本地浏览器会话：

```bash
python launch_browser_for_login.py
```

Windows 下也可以为 JCR 运行：

```powershell
.\launch_jcr_login.bat
```

在打开的浏览器中登录你有权使用的机构或个人账号，确认平台可访问后关闭浏览器。登录状态会保存在 `.playwright_profile/` 中。这个目录是敏感本地文件，不能提交或分享。

如果你直接运行核心脚本但还没有 `.playwright_profile/`，脚本会在终端中提醒你先完成登录设置，并生成 `FIRST_RUN_LOGIN_SETUP.md` 给 Codex、Claude Code、OpenClaw 等客户端读取。该提醒文件已被 `.gitignore` 忽略。

## 先跑一个测试

Windows:

```powershell
.\.venv\Scripts\python tests\test_orcid_extractor.py
```

macOS/Linux:

```bash
./.venv/bin/python tests/test_orcid_extractor.py
```

如果测试通过，说明 Python 依赖和基础环境基本正常。

## 运行 ORCID 提取

确认 `.env` 中已经配置 ORCID 信息后运行：

Windows:

```powershell
.\.venv\Scripts\python orcid_extractor.py
```

macOS/Linux:

```bash
./.venv/bin/python orcid_extractor.py
```

也可以通过命令行参数覆盖 `.env`：

```bash
python orcid_extractor.py --orcid 0000-0002-1825-0097 --client-id APP-YOURID --client-secret YOURSECRET --output my_publications.csv
```

## 运行 Google Scholar 和 Web of Science

```bash
python scholar_playwright.py --user-id <Scholar_ID> --wos-id <WoS_ID> --output output.csv --max-clicks 5
```

默认抓取已经启用 DOI 解析、OpenAlex 元数据增强和通讯作者自动识别：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 5
```

这条命令会先从 Google Scholar 列表页和详情页抓取论文基础信息，再用 OpenAlex 补全结构化元数据，最后只对仍然缺失 DOI 的记录使用 Crossref。OpenAlex 增强会新增 `OpenAlex ID`、`OpenAlex DOI`、`OpenAlex Authors`、`OpenAlex Author Count`、`OpenAlex Corresponding Authors`、`OpenAlex Source`、`OpenAlex Publisher`、`OpenAlex Volume`、`OpenAlex Issue`、`OpenAlex Pages`、`OpenAlex Evidence JSON` 等列。

如果只想先测试部分记录，可以限制 OpenAlex 调用数量：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 1 --openalex-max-records 20
```

如果只想快速抓 Google Scholar，不做 DOI/OpenAlex/通讯作者增强：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 1 --no-fetch-doi --no-openalex-enrich --no-fetch-corresponding
```

参考文献格式导出：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --citation-format apa,gbt2025
```

支持 `apa`、`mla`、`chicago`、`harvard`、`latex`/`bibtex`、`ama`、`gbt`、`gbt2025` 和 `all`。CSV 始终会保存，参考文献文件会额外生成。`gbt2025` 用于 GB/T 7714-2025，在线期刊/会议文献有 DOI 时会输出 `[J/OL]` 或 `[C/OL]`，并以 `DOI: ...` 形式标注 DOI。

也可以一次导出多个格式：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --citation-format apa,gbt,gbt2025
```

作者和通讯作者标注：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --target-author "De-Yi Wang" --author-highlight both
```

`--target-author` 或 `--target-author-position` 会提取目标作者位次，并在作者列表和参考文献导出中高亮。`--corresponding-author` 或 `--corresponding-author-position` 可手动指定通讯作者；默认通讯作者识别会优先复用 OpenAlex enrichment 中的信息。需要关闭时使用 `--no-fetch-corresponding`。

输出排序可由用户选择：

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --output-sort publication-date
```

`--output-sort` 支持 `citations`、`publication-date`、`year` 和 `none`。默认仍为 `citations`，即按 Google Scholar 引用数降序；选择 `publication-date` 时，CSV 和参考文献导出都会按最新发表日期优先排序。

## 从简历或模板一键整理

如果用户只有简历、单位申请模板，或只知道姓名和单位，可以先运行一键导入入口。它会读取 `docx/pdf/txt/md`，自动识别姓名、单位、邮箱、ORCID、Google Scholar ID、论文线索和模板里的填报要求，生成本地 JSON/CSV/Markdown 结果。

默认情况下，工具会先停在“请确认”状态，不会直接抓取。用户检查 `final_summary.md` 无误后，再加 `--yes` 继续自动补全。正式抓取前还必须确认年份范围：用 `--all-years` 表示整理全部年份，或用 `--year 2024` / `--year-from 2020 --year-to 2024` 指定年份。

```bash
python scholar_intake.py --input cv.docx --template job_template.docx --output-dir intake_results
python scholar_intake.py --input cv.docx --template job_template.docx --output-dir intake_results --yes --all-years
```

主要输出包括：

```text
intake_results/intake_profile.json
intake_results/author_candidates.json
intake_results/scrape_plan.json
intake_results/publication_clues.csv
intake_results/final_summary.md
```

如果出现多个同名学者，或单位、模板要求、年份范围等关键信息还没识别完整，工具会继续停在确认状态，并在 `author_candidates.json` 和 `final_summary.md` 中提示需要用户补充或确认。对于 Word 简历，摘要中还会列出检测到的加粗、下划线和星号作者片段；对于 PDF，摘要会提醒用户提供 Word 文件或补充作者标记说明。

如果 Web of Science 需要机构登录，先打开本地持久化浏览器：

```bash
python launch_browser_for_login.py
```

在弹出的浏览器中手动登录你的机构或个人账号。关闭浏览器后，登录状态会保存在本地 `.playwright_profile/` 中。这个目录不能提交或分享。

## 运行 JCR 提取

### JCR / 中科院分区数据来源

分区数据现在支持三类来源：

- 中科院本地分区：用户自行下载或整理数据，放在 `data/cas-local/`，或通过 `--local-partition-file` 指定文件。
- JCR 本地分区：用户自行下载或整理 JCR 数据，放在 `data/jcr-local/`，或通过 `--local-partition-file` 指定文件。
- JCR 实时查询：如果你拥有合法的 Clarivate/JCR 访问权限，可以通过 Playwright 自动化浏览器登录 JCR 网站，查询当前页面可见的最新信息。

实时查询不会绕过访问控制。你仍然需要使用自己有权使用的机构或个人账号。

默认 public release 不附带任何完整的 JCR 或中科院分区原始文件。原因是这类数据文件可能有版权、数据库权利、平台条款、机构授权或再分发限制。如果你只是本地使用，可以把自己的多年份文件放在 `data/jcr-local/`、`data/cas-local/` 或其他本地路径中；如果你确实要把数据文件发布到 GitHub，请先确认来源允许公开再分发，并记录年份、来源、许可证、下载日期和校验信息。

如果用户没有明确指定分区来源，交互式运行会主动询问使用中科院本地分区、JCR 本地分区、JCR 实时查询，还是跳过分区查询。非交互式自动化运行会默认继续 JCR 实时查询；如需中科院分区，请显式添加 `--partition-source cas-local`。

先准备输入文件。可以参考：

```text
examples/jcr_input.example.json
```

输入格式：

```json
[
  {
    "journal_name_or_issn": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "publication_year": 2021
  }
]
```

运行：

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_results.md
```

使用中科院本地分区：

```bash
npm run fetch -- --input examples/jcr_input.example.json --output cas_results.md --partition-source cas-local
npm run fetch -- --journal "Advanced Functional Materials" --year 2024 --output cas_results.md --partition-source cas-local --local-partition-file data/cas-local/cas_2024_partitions.csv
```

使用 JCR 本地分区：

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_local_results.md --partition-source jcr-local
```

自动化或无人值守运行时：

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_results.md --skip-offline-reminder
```

如果你使用 Clarivate/JCR 自动登录，请只在本地 `.env` 或系统环境变量中配置：

```powershell
$env:CLARIVATE_EMAIL="your_email@institution.edu"
$env:CLARIVATE_PASSWORD="your_password"
```

## 输出文件

常见输出包括：

- `*.csv`
- `*.json`
- `*.md`
- `*.html`
- `*.png`
- `*.log`

这些默认都是本地产物。分享或提交前请人工检查，确认没有个人信息、机构访问痕迹、账号信息、cookie、受版权保护的页面内容或不该公开的数据。

## Agentic IDE 支持

这个仓库尽量兼容多种 Agentic IDE 和 coding agent：

- `SKILL.md`：给支持 skill 工作流的工具使用。
- `AGENTS.md`：给通用 coding agent 使用。
- `CLAUDE.md`：给 Claude Code 使用。
- `GEMINI.md`：给 Gemini 或其他代理客户端使用。
- `QUICKSTART.md`：更短的安装和运行步骤。
- `SECURITY.md` 和 `RELEASE_CHECKLIST.md`：安全和发布检查。

## 合规说明

请只在你拥有合法授权的账号、订阅和数据范围内使用本工具。使用时请遵守 Google Scholar、Web of Science、Clarivate JCR、ORCID 的服务条款、访问频率限制、版权要求、机构政策和隐私义务。

## 许可证

本项目采用 Apache License 2.0。版权所有 © 2026 bluessoul。使用、修改或分发本项目时，请保留 `LICENSE`、`NOTICE` 和版权声明，并注明原项目来源。
