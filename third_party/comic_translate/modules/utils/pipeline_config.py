from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from typing import TYPE_CHECKING
from modules.inpainting.lama import LaMa
from modules.inpainting.mi_gan import MIGAN
from modules.inpainting.aot import AOT
from modules.inpainting.schema import Config
from app.ui.messages import Messages
from app.ui.settings.settings_page import SettingsPage

if TYPE_CHECKING:
    from controller import ComicTranslate

inpaint_map = {
    "LaMa": LaMa,
    "MI-GAN": MIGAN,
    "AOT": AOT,
}


def get_inpainter_backend(inpainter_key: str) -> str:
    inpainter_cls = inpaint_map[inpainter_key]
    return getattr(inpainter_cls, "preferred_backend", "onnx")

def get_config(settings_page: SettingsPage):
    strategy_settings = settings_page.get_hd_strategy_settings()
    if strategy_settings['strategy'] == settings_page.ui.tr("Resize"):
        config = Config(hd_strategy="Resize", hd_strategy_resize_limit = strategy_settings['resize_limit'])
    elif strategy_settings['strategy'] == settings_page.ui.tr("Crop"):
        config = Config(hd_strategy="Crop", hd_strategy_crop_margin = strategy_settings['crop_margin'],
                        hd_strategy_crop_trigger_size = strategy_settings['crop_trigger_size'])
    else:
        config = Config(hd_strategy="Original")

    return config

def validate_ocr(main: ComicTranslate):
    # Manga Yomi only exposes the local default OCR engine.
    settings = main.settings_page
    tool = settings.get_tool_selection('ocr')
    if tool not in ('Default', settings.ui.tr('Default')):
        Messages.show_missing_tool_error(main, '本地日文 OCR，请选择 Default')
        return False
    return True


def validate_translator(main: ComicTranslate, target_lang: str):
    from urllib.parse import urlparse
    settings = main.settings_page
    if settings.get_tool_selection('translator') != 'Custom':
        Messages.show_missing_tool_error(main, '自有 API，请选择 Custom')
        return False
    creds = settings.get_credentials(settings.ui.tr('Custom'))
    address = (creds.get('api_url') or '').strip().rstrip('/')
    parsed = urlparse(address)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or address.endswith('/chat/completions') or not (creds.get('model') or '').strip():
        from PySide6 import QtWidgets
        QtWidgets.QMessageBox.warning(main, '翻译服务未配置', '请点击翻译服务，填写 API 基础地址和模型名称。')
        return False
    if parsed.hostname not in ('localhost','127.0.0.1','::1') and not (creds.get('api_key') or '').strip():
        from PySide6 import QtWidgets
        QtWidgets.QMessageBox.warning(main, '缺少 API Key', '请在翻译服务中填写服务提供方的 API Key。')
        return False
    return True


def font_selected(main: ComicTranslate):
    if not main.render_settings().font_family:
        Messages.select_font_error(main)
        return False
    return True

def validate_settings(main: ComicTranslate, target_lang: str):
    if not validate_ocr(main):
        return False
    if not validate_translator(main, target_lang):
        return False
    if not font_selected(main):
        return False
    
    return True
