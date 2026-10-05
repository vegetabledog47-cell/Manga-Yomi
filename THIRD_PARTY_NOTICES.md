# Third-party components

Comic Translate — https://github.com/ogkalu2/comic-translate — Apache License 2.0.
The source snapshot is copied from the user's local comic-translate-main directory. Its original LICENSE and README are preserved in third_party/comic_translate.

Local changes prevent generic settings from saving credentials in plaintext and correctly clear the credentials group; dedicated Windows-encrypted storage is implemented in yomi_credentials.py. Local changes replace the upstream account requirement with validation for local OCR and the configured custom API, isolate QSettings, redirect model/project data paths, and fix RemoteDisconnected download retries and incomplete-read error reporting. Manga Yomi extensions in yomi_core.py and yomi_desktop.py add review, glossary and context behavior at runtime. The upstream detection, OCR, inpainting and rendering implementations remain the foundation.

Other libraries and downloaded models retain their respective upstream licenses. Do not redistribute API credentials or book files.
