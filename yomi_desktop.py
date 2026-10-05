"""Manga Yomi desktop shell and proofreading workspace."""
import os
import sys
import json
import hashlib
import re
from urllib.parse import urlparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['MANGA_YOMI_DATA_DIR']=str(ROOT/'data')
ENGINE=ROOT/'third_party'/'comic_translate'
sys.path.insert(0,str(ENGINE))
from PySide6 import QtWidgets as W,QtCore as C,QtGui as G
from yomi_core import install_extensions,read_memory,write_memory,choose_book,ACTIVE
install_extensions()
from controller import ComicTranslate
from yomi_credentials import load_config,save_config

STATUS={'proposed':'待确认','needs_review':'需复核','verified':'已确认'}

class YomiWindow(ComicTranslate):
    def setWindowTitle(self,title):
        super().setWindowTitle('Manga Yomi | '+title.replace('Comic Translate','漫画翻译'))

    def __init__(self):
        super().__init__()
        self.setWindowIcon(G.QIcon(str(ROOT/'assets'/'manga-yomi.ico')))
        self.dock_ready=False
        self._review_busy=False;self._signature=None
        self._setup_yomi()
        ui=self.settings_page.ui
        ui.translator_combo.clear();ui.translator_combo.addItem('Custom');ui.translator_combo.setCurrentText('Custom')
        ui.ocr_combo.clear();ui.ocr_combo.addItem(ui.tr('Default'))
        ui.save_keys_checkbox.setChecked(False)
        ui.save_keys_checkbox.setEnabled(False)
        self.remember_service=False
        try:
            saved=load_config()
            if saved:
                for key in ('api_url','model','api_key'):ui.credential_widgets['Custom_'+key].setText(saved.get(key,''))
                ui.image_checkbox.setChecked(saved.get('images',False))
                self.remember_service=saved.get('remember',False)
        except (OSError,ValueError):
            self.statusBar().showMessage('无法读取保存的 API 配置，请重新填写并保存。')
        for name in ('sign_in_button','buy_credits_button','sign_out_button','check_update_button'):
            if hasattr(ui,name):getattr(ui,name).setEnabled(False)
        account=W.QWidget();account_layout=W.QVBoxLayout(account)
        heading=W.QLabel('配置翻译服务');heading.setStyleSheet('font-size: 24px;');account_layout.addWidget(heading)
        message=W.QLabel('Manga Yomi 使用自己的 API，不需要登录 Comic Translate。填写 API 地址、模型名称和 Key 后即可翻译。');message.setWordWrap(True);account_layout.addWidget(message)
        configure=W.QPushButton('打开翻译服务配置（Ctrl+K）');configure.clicked.connect(self.service_dialog);account_layout.addWidget(configure);account_layout.addStretch()
        ui.stacked_widget.insertWidget(1,account);ui.stacked_widget.removeWidget(ui.account_page);ui.account_page.hide()
        self.s_combo.setCurrentText(self.tr('Japanese'));self.t_combo.setCurrentText(self.tr('Simplified Chinese'))
        if not self.render_settings().font_family:self.set_font("Microsoft YaHei")
        # Keep fonts and image cleaning available in the original settings UI.
        self.timer=C.QTimer(self);self.timer.timeout.connect(self.refresh_review);self.timer.start(1200)

    def connect_ui_elements(self):
        original=self.image_ctrl.thread_load_images
        def load_with_memory(paths):
            if paths:
                choose_book(paths)
                if hasattr(self,'glossary'):self.load_memory_ui()
            return original(paths)
        self.image_ctrl.thread_load_images=load_with_memory
        original_update=self.project_ctrl.update_ui_from_project
        def update_project_memory(*args,**kwargs):
            result=original_update(*args,**kwargs)
            if self.image_files:
                choose_book(self.image_files)
                if hasattr(self,'glossary'):self.load_memory_ui()
            return result
        self.project_ctrl.update_ui_from_project=update_project_memory
        super().connect_ui_elements()

    def _setup_yomi(self):
        toolbar=W.QWidget(self);toolbar.setObjectName('yomi_actions')
        row=W.QHBoxLayout(toolbar);row.setContentsMargins(12,8,12,8);row.setSpacing(8)
        toolbar.setStyleSheet('QPushButton { padding: 7px 14px; border: 1px solid #58636b; border-radius: 5px; background: #37454f; color: white; } QPushButton:hover { background: #496472; }')
        for label,callback in [('导入漫画 / PDF',self.open_book),('翻译服务',self.service_dialog),('校对与术语',self.show_dock),('导出校对记录',self.export_review),('项目说明',self.open_readme)]:
            button=W.QPushButton(label,toolbar);button.clicked.connect(callback);row.addWidget(button)
            if label=='翻译服务':
                button.setObjectName('yomi_service_button');button.setToolTip('配置 API 地址、模型和 Key（Ctrl+K）')
        row.addStretch()
        self.centralWidget().layout().insertWidget(1,toolbar)
        self.service_shortcut=G.QShortcut(G.QKeySequence('Ctrl+K'),self)
        self.service_shortcut.activated.connect(self.service_dialog)
        self.dock=W.QDockWidget('Manga Yomi · 校对工作台',self);self.dock.setObjectName('yomi_review_dock');self.dock.setMinimumWidth(390)
        self.dock.setAllowedAreas(C.Qt.DockWidgetArea.RightDockWidgetArea|C.Qt.DockWidgetArea.LeftDockWidgetArea)
        tabs=W.QTabWidget();tabs.setStyleSheet('QTabBar::tab { padding: 8px 14px; margin-right: 4px; color: #cccccc; } QTabBar::tab:selected { color: #ffffff; background: #38444c; }');self.dock.setWidget(tabs);self.addDockWidget(C.Qt.DockWidgetArea.RightDockWidgetArea,self.dock)
        review=W.QWidget();layout=W.QVBoxLayout(review)
        self.review_hint=W.QLabel('导入漫画后，先 Detect → Recognize → Translate，再核对译文。');self.review_hint.setWordWrap(True);layout.addWidget(self.review_hint)
        self.review_table=W.QTableWidget(0,4);self.review_table.setHorizontalHeaderLabels(['日文原文','中文译文','状态','备注']);self.review_table.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeMode.Stretch)
        self.review_table.setWordWrap(True);self.review_table.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.review_table.itemChanged.connect(self.edit_review);layout.addWidget(self.review_table)
        row=W.QHBoxLayout()
        for label,callback in [('刷新',lambda:self.refresh_review(force=True)),('确认选中项',self.confirm_selected),('标为需复核',self.flag_selected)]:
            button=W.QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row)
        note=W.QLabel('双击中文单元格修改，按 Enter 或点击其他单元格提交；已有图中文字会同步更新。“确认”只记录核对状态。');note.setWordWrap(True);layout.addWidget(note);tabs.addTab(review,'逐句校对')
        glossary=W.QWidget();lay=W.QVBoxLayout(glossary)
        self._glossary_busy=False
        self.glossary=W.QTableWidget(0,3);self.glossary.setHorizontalHeaderLabels(['日文术语','固定译名','状态']);self.glossary.horizontalHeader().setSectionResizeMode(W.QHeaderView.ResizeMode.Stretch);lay.addWidget(self.glossary)
        self.glossary.itemChanged.connect(self.edit_term)
        buttons=W.QHBoxLayout()
        for label,callback in [('读取候选',self.load_memory_ui),('添加',self.add_term),('确认术语',self.confirm_term),('删除',self.delete_term),('保存',self.save_terms)]:
            b=W.QPushButton(label);b.clicked.connect(callback);buttons.addWidget(b)
        lay.addLayout(buttons)
        self.context=W.QPlainTextEdit();self.context.setPlaceholderText('人物与口吻：每行一条，例如「田中：说话简短，称呼教练为教练」。');lay.addWidget(self.context)
        b=W.QPushButton('保存人物与口吻');b.clicked.connect(self.save_characters);lay.addWidget(b)
        info=W.QLabel('已确认术语会加入后续翻译；候选术语不会自动成为固定译名。每本漫画分别保存记忆。');info.setWordWrap(True);lay.addWidget(info);tabs.addTab(glossary,'术语与人物')
        self.statusBar().showMessage('Manga Yomi · 请配置自己的兼容 API，或先导入漫画进行本地 OCR。')
        self.load_memory_ui()

    def show_dock(self):self.dock.show();self.dock.raise_()

    def open_book(self):
        files,_=W.QFileDialog.getOpenFileNames(self,'导入漫画 / PDF',str(ROOT),'漫画文件 (*.pdf *.png *.jpg *.jpeg *.webp *.cbz *.cbr *.epub);;所有文件 (*)')
        if files:
            self.image_ctrl.thread_load_images(files)

    def open_readme(self):G.QDesktopServices.openUrl(C.QUrl.fromLocalFile(str(ROOT/'README.md')))

    def service_dialog(self):
        ui=self.settings_page.ui
        dialog=W.QDialog(self);dialog.setWindowTitle('Manga Yomi · 翻译服务');dialog.resize(550,300);form=W.QFormLayout(dialog)
        fields={}
        for key,label in [('api_url','API 基础地址'),('model','模型名称'),('api_key','API Key')]:
            edit=W.QLineEdit(ui.credential_widgets['Custom_'+key].text());fields[key]=edit
            if key=='api_key':edit.setEchoMode(W.QLineEdit.EchoMode.Password)
            form.addRow(label,edit)
        hint=W.QLabel('填写兼容 Chat Completions 的服务。基础地址通常以 /v1 结尾，不要追加 /chat/completions。地址与模型自动保存；勾选下方选项可记住 API Key。');hint.setWordWrap(True);form.addRow(hint)
        images=W.QCheckBox('附带漫画图片（需要模型支持图片输入）');images.setChecked(ui.image_checkbox.isChecked());form.addRow(images)
        remember=W.QCheckBox('记住配置和 API Key（下次启动自动填入）');remember.setObjectName('yomi_remember_service');remember.setChecked(self.remember_service);form.addRow(remember)
        privacy=W.QLabel('Key 使用 Windows 当前用户加密保存。取消勾选并保存会清除已保存的 Key，当前会话仍可使用。');privacy.setWordWrap(True);form.addRow(privacy)
        box=W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Save|W.QDialogButtonBox.StandardButton.Cancel);box.accepted.connect(dialog.accept);box.rejected.connect(dialog.reject);form.addRow(box)
        if dialog.exec()==W.QDialog.DialogCode.Accepted:
            url=fields['api_url'].text().strip().rstrip('/')
            if urlparse(url).scheme not in ('https','http') or not urlparse(url).hostname or url.endswith('/chat/completions') or not fields['model'].text().strip():
                W.QMessageBox.warning(self,'配置错误','请填写有效的基础地址与模型名称。');return
            values={key:edit.text().strip() for key,edit in fields.items()};values['api_url']=url
            try:save_config(values,images.isChecked(),remember.isChecked())
            except (OSError,ValueError) as error:
                W.QMessageBox.warning(self,'保存失败','无法保存翻译服务配置：'+str(error));return
            self.remember_service=remember.isChecked()
            for key,value in values.items():ui.credential_widgets['Custom_'+key].setText(value)
            ui.image_checkbox.setChecked(images.isChecked());ui.save_keys_checkbox.setChecked(False)
            self.pipeline.cache_manager.clear_translation_cache()
            self.statusBar().showMessage('翻译服务已配置，API Key 已加密记住。' if self.remember_service else '地址与模型已记住，API Key 仅用于当前会话。')

    def page_key(self):
        if 0<=self.curr_img_idx<len(self.image_files):return self.image_files[self.curr_img_idx]
        return 'unloaded'

    def block_key(self,block):
        coords=getattr(block,'xyxy',None)
        raw=self.page_key()+'|'+str(list(coords) if coords is not None else [])+'|'+block.text
        return hashlib.sha256(raw.encode()).hexdigest()

    def refresh_review(self,force=False):
        if self._batch_active or (self.current_worker is not None and self.threadpool.activeThreadCount()):return
        signature=(self.page_key(),tuple((b.text,b.translation,getattr(b,'yomi_status','proposed'),str(getattr(b,'yomi_notes',[]))) for b in self.blk_list))
        if signature==self._signature and not force:return
        self._signature=signature;self._review_busy=True
        try:
            memory=read_memory();self.review_table.setRowCount(len(self.blk_list))
            for i,b in enumerate(self.blk_list):
                prior=memory['reviews'].get(self.block_key(b))
                if prior and prior['translation']==b.translation and not hasattr(b,'yomi_status'):
                    b.yomi_status=prior['status'];b.yomi_notes=prior['notes']
                status=getattr(b,'yomi_status','proposed')
                notes=getattr(b,'yomi_notes',getattr(b,'yomi_ocr_notes',[]))
                if getattr(b,'yomi_ocr_notes',[]) and not b.translation:status='needs_review'
                for j,text in enumerate((b.text,b.translation,STATUS.get(status,'待确认'),'；'.join(notes))):
                    item=W.QTableWidgetItem(text)
                    if j in (0,2):item.setFlags(item.flags() & ~C.Qt.ItemFlag.ItemIsEditable)
                    if status=='needs_review':item.setBackground(G.QColor('#5b4026'))
                    if status=='verified':item.setBackground(G.QColor('#214b43'))
                    self.review_table.setItem(i,j,item)
            self.review_table.resizeRowsToContents()
            pending=sum(getattr(b,'yomi_status','proposed')!='verified' for b in self.blk_list)
            self.review_hint.setText(f'当前页 {len(self.blk_list)} 个气泡 · {pending} 项待确认。可直接编辑中文与备注。')
            self.persist_review()
        finally:self._review_busy=False

    def review_matches_page(self):
        return self._signature is not None and self._signature[0]==self.page_key() and len(self._signature[1])==len(self.blk_list) and tuple((b.text,b.translation) for b in self.blk_list)==tuple((row[0],row[1]) for row in self._signature[1])

    def sync_review_text(self,block,old_text):
        from app.ui.canvas.text_item import TextBlockItem
        candidates=list(self.image_viewer.text_items)
        for item in self.image_viewer._scene.items():
            if isinstance(item,TextBlockItem) and item not in candidates:candidates.append(item)
        matched=[item for item in candidates if self.text_ctrl._find_text_block_for_item(item) is block]
        if not matched:
            normalize=lambda text:re.sub(r'\s+','',text)
            same=[item for item in candidates if isinstance(item,TextBlockItem) and normalize(item.toPlainText())==normalize(old_text)]
            unique=sum(normalize(b.translation)==normalize(old_text) for b in self.blk_list)==0
            if len(same)==1 and unique:matched=same
        for item in matched:
            self.text_ctrl.apply_text_from_command(item,block.translation,blk=block)
            item.update()
        self.image_viewer.viewport().update()
        if matched:self.statusBar().showMessage('译文已同步到图中文字。')
        else:self.statusBar().showMessage('译文已保存；未找到对应画布文字，请先完成渲染。')
        return bool(matched)

    def edit_review(self,item):
        if not self._review_busy and not self.review_matches_page():
            self.refresh_review(force=True);return
        if self._review_busy or item.row()>=len(self.blk_list):return
        b=self.blk_list[item.row()]
        if item.column()==1:
            old_text=b.translation
            b.translation=item.text();b.yomi_status='proposed'
            self.sync_review_text(b,old_text)
            if self.curr_tblock is b:
                self.t_text_edit.blockSignals(True);self.t_text_edit.setPlainText(b.translation);self.t_text_edit.blockSignals(False)
        elif item.column()==3:b.yomi_notes=[item.text()] if item.text().strip() else []
        self.mark_project_dirty();self.persist_review();self.refresh_review(force=True)

    def set_selected_status(self,status):
        if not self.review_matches_page():self.refresh_review(force=True);return
        rows={i.row() for i in self.review_table.selectedIndexes()}
        if not rows:return
        for i in rows:
            b=self.blk_list[i]
            if status=='verified' and not b.translation.strip():
                W.QMessageBox.warning(self,'无法确认','空译文不能标为已确认。');return
        for i in rows:self.blk_list[i].yomi_status=status
        self.mark_project_dirty()
        self.persist_review();self.refresh_review(force=True)
    def confirm_selected(self):self.set_selected_status('verified')
    def flag_selected(self):self.set_selected_status('needs_review')

    def persist_review(self):
        if not self.blk_list:return
        memory=read_memory()
        for b in self.blk_list:memory['reviews'][self.block_key(b)]={'page':self.page_key(),'source':b.text,'translation':b.translation,'status':getattr(b,'yomi_status','proposed'),'notes':getattr(b,'yomi_notes',[])}
        write_memory(memory)

    def load_memory_ui(self):
        data=read_memory();self._glossary_busy=True;self.glossary.setRowCount(0)
        for t in data['terms']:
            row=self.glossary.rowCount();self.glossary.insertRow(row)
            for j,v in enumerate((t['source'],t['target'],'已确认' if t['status']=='confirmed' else '候选')):
                item=W.QTableWidgetItem(v)
                if j==2:item.setFlags(item.flags() & ~C.Qt.ItemFlag.ItemIsEditable)
                self.glossary.setItem(row,j,item)
        self.context.setPlainText(chr(10).join(data['characters']));self._signature=None;self._glossary_busy=False

    def edit_term(self,item):
        if self._glossary_busy or item.column() not in (0,1):return
        status=self.glossary.item(item.row(),2)
        if status is not None:status.setText('候选')

    def add_term(self):
        r=self.glossary.rowCount();self.glossary.insertRow(r)
        for j,t in enumerate(('','','候选')):
            item=W.QTableWidgetItem(t)
            if j==2:item.setFlags(item.flags() & ~C.Qt.ItemFlag.ItemIsEditable)
            self.glossary.setItem(r,j,item)

    def confirm_term(self):
        for r in {i.row() for i in self.glossary.selectedIndexes()}:
            if self.glossary.item(r,0).text().strip() and self.glossary.item(r,1).text().strip():self.glossary.item(r,2).setText('已确认')
        self.save_terms()
    def delete_term(self):
        for r in sorted({i.row() for i in self.glossary.selectedIndexes()},reverse=True):self.glossary.removeRow(r)
        self.save_terms()
    def save_terms(self):
        terms=[];seen=set()
        for r in range(self.glossary.rowCount()):
            source=self.glossary.item(r,0).text().strip();target=self.glossary.item(r,1).text().strip()
            if not source or not target:continue
            if source in seen:W.QMessageBox.warning(self,'术语重复','同一日文术语只能有一个固定译名。');return
            seen.add(source);terms.append({'source':source,'target':target,'status':'confirmed' if self.glossary.item(r,2).text()=='已确认' else 'proposed'})
        data=read_memory();data['terms']=terms;write_memory(data);self.pipeline.cache_manager.clear_translation_cache();self.statusBar().showMessage('术语已保存。已确认词条用于后续翻译。')
    def save_characters(self):
        data=read_memory();data['characters']=[x.strip() for x in self.context.toPlainText().splitlines() if x.strip()];write_memory(data);self.pipeline.cache_manager.clear_translation_cache();self.statusBar().showMessage('人物与口吻已保存。')

    def export_review(self):
        self.persist_review();filename,_=W.QFileDialog.getSaveFileName(self,'导出校对记录',str(ROOT/'review.json'),'JSON (*.json)')
        if filename:
            try:
                data=read_memory();Path(filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:
                W.QMessageBox.warning(self,'导出失败','无法写入校对记录：'+str(error));return
            self.statusBar().showMessage('校对记录已导出。')

def main():
    import logging
    (ROOT/'data').mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT/'data'/'desktop.log',level=logging.WARNING)
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('MangaYomi.Desktop')
    app=W.QApplication(sys.argv);app.setWindowIcon(G.QIcon(str(ROOT/'assets'/'manga-yomi.ico')));app.setApplicationName('Manga Yomi');app.setOrganizationName('MangaYomi');app.setFont(G.QFont('Microsoft YaHei',10))
    from comic import load_translation
    load_translation(app,'简体中文')
    window=YomiWindow();window.show()
    if "--configure" in sys.argv:C.QTimer.singleShot(350,window.service_dialog)
    return app.exec()
if __name__=='__main__':raise SystemExit(main())
