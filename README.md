# Manga Yomi

日漫翻译与校对工具，支持图片、PDF 和漫画压缩包。

## 功能

- 文字检测、日文 OCR、擦字与中文嵌字
- 逐句校对、修改译文同步画布、校对记录导出
- 固定译名、人物口吻与跨页上下文记忆
- 二次 OCR 候选、人名一致性和跨框断句提示
- 自定义翻译 API，支持加密记住 API Key
- JPG / PNG 单页输出与多页 PDF 导出

## 安装与启动

Windows，Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe yomi_desktop.py
```

已配置环境的本机可直接双击 `Manga Yomi.lnk`。快捷方式使用本机路径，换电脑后请按上述命令启动。首次使用会下载所需模型。

## 配置翻译服务

点击 **翻译服务**，或按 `Ctrl+K`。

| 配置项 | DeepSeek 示例 |
| --- | --- |
| API 基础地址 | `https://api.deepseek.com` |
| 模型名称 | `deepseek-flash` |
| API Key | 自己申请的密钥 |

基础地址不要包含 `/chat/completions`。纯文字翻译关闭“附带漫画图片”；开启时需使用支持图像的模型。

勾选“记住配置和 API Key”后保存，下次启动自动填入。密钥使用当前 Windows 用户加密保存；取消勾选并保存可清除。

## 使用

1. 导入 JPG、PDF 或漫画文件，设置源语言和目标语言。
2. 切换 **手动**，依次点击 **检测 → 识别**，检查并修正日文原文。
3. 点击 **翻译**，在右侧逐句校对。双击中文修改，按 Enter 提交；可匹配的画布文字会同步更新。
4. 点击 **分割 → 清除 → 渲染**，检查擦字效果、字号和排版。
5. 保存 `.ctpr` 项目以继续编辑，或通过左侧保存／导出按钮输出图片、PDF。

批量处理可切换 **自动**，点击 **全部翻译**。有页面跳过时查看 **报告**。

### 术语与人物

翻译后点击 **读取候选**，或手动添加日文和固定译名。只有确认的词条用于后续翻译；修改后需要重新确认。人物口吻每行一条，填写后点击 **保存人物与口吻**。

记忆按漫画分别保存，参考最近五次成功翻译的摘要。建议按页序处理。**读取候选会重载列表，先保存手工修改。**

## Manga Yomi Skill

Skill 位于 `manga-yomi/`，核心指令是 `SKILL.md`，输出格式及 PDF 流程在 `references/`。可原生安装到支持 Agent Skills 的工具，也可作为其他聊天平台的自定义指令使用。

### Claude：上传 Skill

1. 打开 **Customize → Skills**，选择新增并上传 Skill。
2. 上传本项目提供的 `manga-yomi-skill.zip` 并启用。它只包含 Skill 文件夹，不是整个桌面程序包。
3. 上传漫画图片或 PDF，要求“使用 Manga Yomi 翻译并校对前两页”。

入口是否可用取决于账户与组织设置。参见 [Claude 官方说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)。

### ChatGPT：项目指令

1. 新建一个名为 **Manga Yomi** 的项目。
2. 把 `SKILL.md` 中从 `# Manga Yomi` 开始的正文复制到项目指令；也可上传完整文件，并在项目指令中要求按它执行。
3. 上传 `references/` 中的说明文件，作为输出格式与处理流程参考。
4. 在项目聊天中上传漫画，以及已有的 `yomi-memory.json`，然后发出翻译请求。

这是通过项目指令复用工作流，不是安装桌面程序或自动执行 Python 脚本。参见 [ChatGPT 项目说明](https://learn.chatgpt.com/docs/projects)。

### Gemini：创建 Gem

1. 在 Gemini 网页版新建 Gem，名称填 **Manga Yomi**。
2. 将 `SKILL.md` 正文复制到 Instructions，把 `references/` 文件添加到 Knowledge。
3. 保存后，在该 Gem 的聊天中上传漫画和已有记忆文件，再提出翻译请求。

参见 [Gemini Gems 官方说明](https://support.google.com/gemini/answer/15146780?hl=en)。

### DeepSeek、通义千问及其他聊天平台

没有原生 Skill 入口时，可在新聊天中粘贴 `SKILL.md` 正文，补充所需的参考文件内容，再发送下面的请求。使用支持图像阅读的模型可直接上传图片；仅支持文本时，先用桌面版 OCR，粘贴识别出的日文。

这一方式复用翻译规则，不会自动加载文件夹、运行脚本或调用桌面版 API。换聊天时重新提供规则和记忆。

### Codex

将整个 `manga-yomi/` 文件夹安装到 Codex 的技能目录，再使用 `$manga-yomi` 调用。当前电脑已配置，可以直接调用。

### 请求示例

```text
按 Manga Yomi 的规则翻译我上传的漫画，只处理前两页。
使用自然的简体中文，结合上下文，统一人物称呼。
先输出“编号 / 日文 / 中文 / 状态 / 备注”对照表。
看不清的字和不确定的人名标记为需复核，不要擅自补全。
完成后整理本次人物、术语和剧情摘要；先让我确认，再输出最终稿。
```

续译时上传上次的 `yomi-memory.json`。若平台不能生成文件，可让它输出记忆 JSON 文本，复制保存后在下次聊天中提供。

网页聊天需要上传文件，不能仅凭 `D:\...` 路径读取本机漫画。PDF 图像读取、运行辅助脚本及生成下载文件取决于平台能力；扫描 PDF 无法读取时先提供逐页图片。聊天 Skill 不自动擦字嵌字，漫画成品排版使用桌面程序。桌面版的自动二次 OCR 检查也不会因复制指令而在网页聊天中运行。

## 注意事项

- 手写字、拟声词和复杂排版需要人工检查；OCR 候选和断句关联可能出错。
- “已确认”记录校对状态，不会阻止未确认页面导出。
- 自动擦字可能影响画面细节，导出前检查成品。
- 翻译格式错误最多请求三次，重试按 API 服务计费。

## 开发

```powershell
.\.venv\Scripts\python.exe tests/test_desktop.py
```

`yomi_desktop.py`：界面与校对；`yomi_core.py`：翻译和记忆；`yomi_quality.py`：识别检查；`yomi_credentials.py`：配置存储。

## 致谢与许可

基础漫画处理引擎来自 [Comic Translate](https://github.com/ogkalu2/comic-translate)，遵循 Apache-2.0 许可。原源码和许可证保留在 `third_party/comic_translate/`，其他组件说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
