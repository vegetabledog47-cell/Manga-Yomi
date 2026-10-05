# 与 comic-translate 配合

原项目在批处理 Export 设置中可开启原文与译文导出；生成 `{页名}_raw.json` 和 `{页名}_translated.json`，内容均为 `block_N` 到字符串的映射。Manga Yomi 将原文映射转换为结构化审阅稿，保留所有键和原文；可把现有译文用作 initial_translation。

先运行 prepare，再由 skill 翻译和审阅输出草稿；prepare 生成的空译文不能作为完成结果。
```powershell
python scripts/yomi_bridge.py prepare --raw page_raw.json --out yomi-page.json --page-id p001
python scripts/yomi_bridge.py export --raw page_raw.json --review yomi-page.json --out page_translated.json
```
默认 export 要求所有项均为 verified；存在 proposed / needs_review 时拒绝导出。用户需要草稿则显式加 `--allow-draft`，导出时会打印未确认项数量。

脚本只生成兼容 JSON，不修改原漫画或原项目。当前未验证原项目支持导入修改后的 JSON；应在其手动模式逐条回填中文译文。不要声称已实现自动回填。
