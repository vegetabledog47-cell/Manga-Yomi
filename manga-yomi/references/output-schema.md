# 输出约定

`yomi-page.json`:
```json
{"page_id":"p001","blocks":[{"id":"block_0","source":"原文","corrected_source":"原文","translation":"译文","status":"proposed","speaker":null,"notes":[]} ]}
```
`id` 在 JSON 模式中必须与原始键一一对应；图片模式采用页号和气泡号。`source` 永远保留原始值。可额外附上 `position`、`initial_translation`、`change_reason`、`alternatives`。状态只能为 verified / proposed / needs_review。verified 不代表专业译者背书，备注必须说明确认依据。

`yomi-memory.json`:
```json
{"version":1,"confirmed":{"terms":[],"characters":[],"facts":[]},"proposed":{"terms":[],"characters":[],"facts":[]},"recent_pages":[]}
```
术语记录用 source / target / evidence；人物用 name / aliases / voice / evidence；事实用 text / evidence。证据包括页号、气泡号或用户确认。recent_pages 用 page_id / summary，只维护最近五页。不要把推测写进 confirmed，也不要覆盖用户确认的译名；冲突列入 review.md。

review.md 记录输入来源、阅读顺序依据、OCR 修正、翻译修改理由、待确认事项、检查方法与局限。AI 自查和人工核对分别记录。
