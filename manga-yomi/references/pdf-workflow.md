# PDF 翻译

运行环境：优先用技能所在项目根目录 `.venv/Scripts/python.exe`（Windows），否则使用安装了 pypdfium2、Pillow、reportlab 的 Python。脚本路径相对本 skill 目录。

## 准备
```powershell
& 'D:\Manga Yomi\.venv\Scripts\python.exe' 'D:\Manga Yomi\manga-yomi\scripts\yomi_pdf.py' prepare '输入.pdf' --out '新建页面目录'
```
可选 --start / --end 指定 1 起始页号，--dpi 默认 160（72..300）。输出必须为未存在的目录。加密或损坏 PDF 失败时报告原因，不假装翻译。

查看 manifest.json 并逐页查看 PNG。扫描 PDF 的 text_hint 通常为空，不能把它当作没有对白；有文本层时也不能直接用提取顺序作为阅读顺序。先识别分镜和气泡，再翻译。大文件按连续页范围分批，保持原页号与跨批记忆，注明翻译范围。

## 翻译保存
保存 review.json 为 {"pages":[{"page_id":"p001","blocks":[{"id":"p001_b001","source":"日文","translation":"中文","status":"proposed","notes":[]}]}]}。pages 必须与 manifest 中页号和顺序一致。无文字页面仍记录一个 source 为 ""、translation 为 "本页无可翻译文字" 的明确审阅项。

译文按 skill 的 OCR、人物、术语、歧义流程检查。写入 memory.json 和 review.md。不要因为需要导出就把 proposed 改成 verified。

## 导出
```powershell
& 'D:\Manga Yomi\.venv\Scripts\python.exe' 'D:\Manga Yomi\manga-yomi\scripts\yomi_pdf.py' compose --manifest '页面目录\manifest.json' --review 'review.json' --out '中文对照.pdf' --allow-draft
```
未确认译文用 --allow-draft，PDF 标注待确认；完成核对后才导出确认稿。脚本输出每页原图及日中对照，中文自动换行并在需要时分页。它不调用翻译 API：翻译由使用 skill 的 Codex 完成。

导出后重新渲染 PDF，检查中文、日文、分页和是否漏项。这个模式保留原漫画，输出对照阅读版；自动擦字和嵌回气泡不属于本脚本能力。
