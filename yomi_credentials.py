"""Local API preferences; keys encrypted for the current Windows user."""
import base64
import ctypes
from ctypes import wintypes
import json
from pathlib import Path

CONFIG_PATH=Path(__file__).resolve().parent/'data'/'translation-service.json'

class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def _protect(value, decrypt=False):
    raw=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(raw,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        result=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output))
    else:
        result=crypt.CryptProtectData(ctypes.byref(source),ctypes.c_wchar_p('Manga Yomi API Key'),None,None,None,1,ctypes.byref(output))
    if not result:raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))

def save_config(values, images, remember):
    data={'version':1,'api_url':values['api_url'],'model':values['model'],'images':bool(images),'remember':bool(remember)}
    if remember and values.get('api_key'):
        data['encrypted_key']=base64.b64encode(_protect(values['api_key'].encode('utf-8'))).decode('ascii')
    CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
    temp=CONFIG_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(CONFIG_PATH)

def load_config():
    if not CONFIG_PATH.exists():return None
    data=json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if data.get('version')!=1:raise ValueError('Unsupported API preferences')
    data['api_key']=''
    if data.get('remember') and data.get('encrypted_key'):
        data['api_key']=_protect(base64.b64decode(data['encrypted_key']),decrypt=True).decode('utf-8')
    return data
