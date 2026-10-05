from pathlib import Path
import sys
import tempfile
import json
import unittest
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import yomi_desktop as desktop
import yomi_core as core
from modules.utils.textblock import TextBlock
from modules.utils.file_handler import ensure_prepared_path_materialized

class DesktopChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=desktop.W.QApplication.instance() or desktop.W.QApplication([])
        cls.scratch=tempfile.TemporaryDirectory()
        cls.old=core.ACTIVE;core.ACTIVE=Path(cls.scratch.name)/'memory.json'
        cls.window=desktop.YomiWindow()
    @classmethod
    def tearDownClass(cls):
        cls.window._skip_close_prompt=True;cls.window.close();core.ACTIVE=cls.old;cls.scratch.cleanup()
    def setUp(self):core.write_memory(core.empty_memory())
    def test_window(self):
        self.assertIn('Manga Yomi',self.window.windowTitle())
        self.assertEqual(self.window.dock.widget().count(),2)
        self.assertEqual(self.window.settings_page.get_tool_selection('translator'),'Custom')
    def test_encrypted_service_preferences(self):
        from unittest.mock import patch
        import yomi_credentials as credentials
        path=Path(self.scratch.name)/'service.json'
        values={'api_url':'https://api.deepseek.com','model':'test-model','api_key':'test-secret-do-not-use'}
        with patch.object(credentials,'CONFIG_PATH',path):
            credentials.save_config(values,False,True)
            self.assertNotIn(values['api_key'],path.read_text(encoding='utf-8'))
            saved=credentials.load_config()
            self.assertEqual(saved['api_key'],values['api_key'])
            self.assertTrue(saved['remember'])
            credentials.save_config(values,False,False)
            self.assertNotIn('encrypted_key',path.read_text(encoding='utf-8'))
            saved=credentials.load_config()
            self.assertEqual(saved['api_key'],'')
            self.assertEqual(saved['model'],'test-model')

    def test_toolbar_actions(self):
        from unittest.mock import patch
        from PySide6.QtTest import QTest
        w=self.window
        toolbar=w.findChild(desktop.W.QWidget,'yomi_actions')
        buttons={b.text():b for b in toolbar.findChildren(desktop.W.QPushButton)}
        self.assertEqual(len(buttons),5)
        with patch.object(desktop.W.QFileDialog,'getOpenFileNames',return_value=([],'')) as opened:
            QTest.mouseClick(buttons['导入漫画 / PDF'],desktop.C.Qt.MouseButton.LeftButton)
            opened.assert_called_once()
        w.dock.hide()
        QTest.mouseClick(buttons['校对与术语'],desktop.C.Qt.MouseButton.LeftButton)
        self.assertFalse(w.dock.isHidden())
        with patch.object(desktop.G.QDesktopServices,'openUrl',return_value=True) as opened:
            QTest.mouseClick(buttons['项目说明'],desktop.C.Qt.MouseButton.LeftButton)
            self.assertTrue(Path(opened.call_args.args[0].toLocalFile()).is_file())
        output=Path(self.scratch.name)/'review-export.json'
        with patch.object(desktop.W.QFileDialog,'getSaveFileName',return_value=(str(output),'')):
            QTest.mouseClick(buttons['导出校对记录'],desktop.C.Qt.MouseButton.LeftButton)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['version'],1)

    def test_service_save_and_cancel(self):
        from unittest.mock import patch
        w=self.window;widgets=w.settings_page.ui.credential_widgets
        old={k:widgets['Custom_'+k].text() for k in ('api_url','model','api_key')}
        old_remember=w.remember_service;old_images=w.settings_page.ui.image_checkbox.isChecked()
        def accept():
            dialog=self.app.activeModalWidget()
            edits=dialog.findChildren(desktop.W.QLineEdit)
            for edit,value in zip(edits,('https://api.deepseek.com/','test-model','test-key')):edit.setText(value)
            dialog.findChild(desktop.W.QCheckBox,'yomi_remember_service').setChecked(True)
            dialog.accept()
        try:
            with patch.object(desktop,'save_config') as saved:
                desktop.C.QTimer.singleShot(80,accept);w.service_dialog()
                self.assertEqual(saved.call_args.args[0]['api_url'],'https://api.deepseek.com')
                self.assertTrue(saved.call_args.args[2])
                self.assertTrue(w.remember_service)
            with patch.object(desktop,'save_config') as saved:
                desktop.C.QTimer.singleShot(80,lambda:self.app.activeModalWidget().reject());w.service_dialog()
                saved.assert_not_called()
        finally:
            for k,v in old.items():widgets['Custom_'+k].setText(v)
            w.remember_service=old_remember;w.settings_page.ui.image_checkbox.setChecked(old_images)

    def test_confirm_flag_and_stale_review(self):
        w=self.window;w.image_files=['page-a.png','page-b.png'];w.curr_img_idx=0
        b=TextBlock(text='はい',translation='是');w.blk_list=[b]
        w.refresh_review(force=True);w.review_table.selectRow(0);w.confirm_selected()
        self.assertEqual(b.yomi_status,'verified')
        w.review_table.selectRow(0);w.flag_selected()
        self.assertEqual(b.yomi_status,'needs_review')
        other=TextBlock(text='いいえ',translation='否');w.curr_img_idx=1;w.blk_list=[other]
        w.review_table.item(0,1).setText('stale edit')
        self.assertEqual(other.translation,'否')
        self.assertEqual(w.review_table.item(0,1).text(),'否')
        w.blk_list=[]

    def test_glossary_buttons_and_edit(self):
        from PySide6.QtTest import QTest
        w=self.window;w.load_memory_ui();tabs=w.dock.widget();tabs.setCurrentIndex(1)
        buttons={b.text():b for b in tabs.widget(1).findChildren(desktop.W.QPushButton)}
        QTest.mouseClick(buttons['添加'],desktop.C.Qt.MouseButton.LeftButton)
        w.glossary.item(0,0).setText('監督');w.glossary.item(0,1).setText('教练');w.glossary.selectRow(0)
        QTest.mouseClick(buttons['确认术语'],desktop.C.Qt.MouseButton.LeftButton)
        self.assertEqual(core.read_memory()['terms'][0]['status'],'confirmed')
        w.glossary.item(0,1).setText('监督')
        self.assertEqual(w.glossary.item(0,2).text(),'候选')
        QTest.mouseClick(buttons['保存'],desktop.C.Qt.MouseButton.LeftButton)
        self.assertEqual(core.read_memory()['terms'][0]['status'],'proposed')
        w.glossary.selectRow(0);QTest.mouseClick(buttons['删除'],desktop.C.Qt.MouseButton.LeftButton)
        self.assertEqual(core.read_memory()['terms'],[])
        tabs.setCurrentIndex(0)

    def test_switch_book_during_translation(self):
        blocks=[TextBlock(text='はい',translation='original')]
        original=core.ACTIVE
        class Stub:
            target_lang='Simplified Chinese'
            def _perform_translation(self,*args):
                core.ACTIVE=Path(original.parent)/'different-book.json'
                return json.dumps({'blocks':{'block_0':{'translation':'是','status':'proposed','notes':[]}}})
        try:
            with self.assertRaises(ValueError):core.translate_reviewed(Stub(),blocks,None,'')
            self.assertEqual(blocks[0].translation,'original')
            self.assertFalse(core.ACTIVE.exists())
        finally:core.ACTIVE=original

    def test_review_updates_existing_canvas_text(self):
        from unittest.mock import patch,Mock
        w=self.window;w.image_files=['canvas-page.png'];w.curr_img_idx=0
        b=TextBlock(text='はい',translation='是');w.blk_list=[b];w.refresh_review(force=True)
        item=Mock()
        with patch.object(w.image_viewer,'text_items',[item]), patch.object(w.text_ctrl,'_find_text_block_for_item',return_value=b), patch.object(w.text_ctrl,'apply_text_from_command') as applied:
            w.review_table.item(0,1).setText('好的')
            applied.assert_called_once_with(item,'好的',blk=b)
        w.blk_list=[]

    def test_pdf_export(self):
        from unittest.mock import patch
        import pypdfium2 as pdfium
        w=self.window
        paths=[]
        for i in range(2):
            p=Path(self.scratch.name)/f'export-{i}.png';Image.new('RGB',(200,280),'white').save(p);paths.append(str(p))
        w.image_files=paths
        output=Path(self.scratch.name)/'export.pdf'
        states={p:{'viewer_state':{}} for p in paths}
        with patch.object(w,'load_image',return_value=np.full((280,200,3),255,dtype=np.uint8)):
            w.project_ctrl.save_and_make_worker([{'page_indices':[0,1],'output_path':str(output)}],states)
        doc=pdfium.PdfDocument(str(output))
        try:self.assertEqual(len(doc),2)
        finally:doc.close()

    def test_quality_hints(self):
        from yomi_quality import quality_context
        blocks=[TextBlock(text_bbox=np.array([0,0,20,60]),text='猫美さん'),TextBlock(text_bbox=np.array([100,0,120,60]),text='猫実さん'),TextBlock(text_bbox=np.array([200,0,220,60]),text='早く行かないと遅'),TextBlock(text_bbox=np.array([400,100,420,160]),text='れっ．．．')]
        memory=core.empty_memory();memory['terms']=[{'source':'猫実','target':'猫实','status':'confirmed'}]
        quality=quality_context(blocks,memory)
        self.assertTrue(quality['ocr_checks']['block_0']['name_candidates'])
        self.assertTrue(quality['ocr_checks']['block_1']['notes'])
        self.assertEqual(quality['related_dialogue'][0]['keys'],['block_2','block_3'])

    def test_ocr_comparison_preserves_source(self):
        from yomi_quality import review_ocr
        from types import SimpleNamespace
        block=TextBlock(text_bbox=np.array([10,10,40,70]),text='今度肉まん脅れよな')
        def original(processor,image,blocks):blocks[0].text='今度肉まん奢れよな';return blocks
        review_ocr(SimpleNamespace(source_lang_english='Japanese'),np.full((100,100,3),255,dtype=np.uint8),[block],original)
        self.assertEqual(block.text,'今度肉まん脅れよな')
        self.assertEqual(block.yomi_ocr_alternatives,['今度肉まん奢れよな'])

    def test_real_canvas_review_sync(self):
        from app.ui.canvas.text_item import TextBlockItem
        w=self.window;w.image_files=['real-canvas.png'];w.curr_img_idx=0
        b=TextBlock(text_bbox=np.array([100,100,200,200]),text='はい',translation='原来的译文')
        w.blk_list=[b]
        item=TextBlockItem(text='原来的译文',font_family='Microsoft YaHei',font_size=12,render_color=desktop.G.QColor('black'))
        # Deliberately moved text; exact coordinates no longer match the block.
        item.setPos(130,130);w.image_viewer._scene.addItem(item)
        w.refresh_review(force=True)
        w.review_table.item(0,1).setText('修改后的译文')
        self.assertEqual(item.toPlainText(),'修改后的译文')
        self.assertEqual(b.yomi_status,'proposed')
        w.review_table.selectRow(0);w.confirm_selected()
        self.assertEqual(b.yomi_status,'verified')
        self.assertEqual(item.toPlainText(),'修改后的译文')
        w.image_viewer._scene.removeItem(item);w.blk_list=[]

    def test_configuration_button(self):
        from PySide6.QtTest import QTest
        button=self.window.findChild(desktop.W.QPushButton,'yomi_service_button')
        self.assertIsNotNone(button)
        observed=[]
        def inspect():
            dialog=self.app.activeModalWidget()
            observed.append(bool(dialog) and '翻译服务' in dialog.windowTitle() and dialog.findChild(desktop.W.QCheckBox,'yomi_remember_service') is not None)
            if dialog:dialog.reject()
        desktop.C.QTimer.singleShot(150,inspect)
        QTest.mouseClick(button,desktop.C.Qt.MouseButton.LeftButton)
        self.assertEqual(observed,[True])
    def test_local_validation_without_upstream_login(self):
        from unittest.mock import patch
        from modules.utils.pipeline_config import validate_ocr,validate_translator,validate_settings
        s=self.window.settings_page
        widgets=s.ui.credential_widgets
        old={k:widgets['Custom_'+k].text() for k in ('api_url','model','api_key')}
        try:
            for k,v in {'api_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':'unit-test-placeholder'}.items():widgets['Custom_'+k].setText(v)
            with patch.object(s,'is_logged_in',side_effect=AssertionError('Upstream login must not be queried')):
                self.assertTrue(validate_ocr(self.window))
                self.assertTrue(validate_translator(self.window,'Simplified Chinese'))
                self.assertTrue(validate_settings(self.window,'Simplified Chinese'))
        finally:
            for k,v in old.items():widgets['Custom_'+k].setText(v)

    def test_deepseek_request_shape(self):
        from unittest.mock import patch,Mock
        from modules.translation.llm.custom import CustomTranslation
        engine=CustomTranslation();engine.api_base_url='https://api.deepseek.com'
        response=Mock();response.json.return_value={'choices':[{'message':{'content':'{}'}}]}
        with patch('modules.translation.llm.gpt.requests.post',return_value=response) as post:
            engine._make_api_request({'messages':[{'role':'system','content':[{'type':'text','text':'Return JSON'}]}],'max_completion_tokens':5000},{})
            payload=json.loads(post.call_args.kwargs['data'])
            self.assertNotIn('max_completion_tokens',payload)
            self.assertEqual(payload['max_tokens'],5000)
            self.assertEqual(payload['messages'][0]['content'],'Return JSON')
            self.assertEqual(payload['thinking']['type'],'disabled')
    def test_glossary_confirmation(self):
        m=core.empty_memory();m['terms']=[{'source':'ホームラン','target':'本垒打','status':'confirmed'},{'source':'監督','target':'教练','status':'proposed'}]
        context=json.loads(core.context_text(m))
        self.assertEqual(len(context['confirmed_terms']),1)
        self.assertEqual(context['confirmed_terms'][0]['target'],'本垒打')
    def test_missing_block_no_mutation(self):
        blocks=[TextBlock(text='はい',translation='original'),TextBlock(text='いいえ',translation='original')]
        class Stub:
            target_lang='Simplified Chinese'
            def _perform_translation(self,*args):return json.dumps({'blocks':{'block_0':{'translation':'是','status':'proposed','notes':[]}}})
        with self.assertRaises(ValueError):core.translate_reviewed(Stub(),blocks,None,'')
        self.assertEqual([b.translation for b in blocks],['original','original'])
    def test_invalid_response_retry(self):
        from unittest.mock import Mock
        blocks=[TextBlock(text='はい',translation='original')]
        valid=json.dumps({'blocks':{'block_0':{'translation':'是','status':'proposed','notes':[]}}})
        engine=Mock(target_lang='Simplified Chinese',spec=['target_lang','_perform_translation'])
        engine._perform_translation.side_effect=['{"blocks":', '{"blocks":{},"blocks":{}}',valid]
        core.translate_reviewed(engine,blocks,None,'')
        self.assertEqual(engine._perform_translation.call_count,3)
        self.assertEqual(blocks[0].translation,'是')
        self.assertIn('Previous response failed validation',engine._perform_translation.call_args.args[0])

    def test_network_error_not_retried(self):
        from unittest.mock import Mock
        engine=Mock(target_lang='Simplified Chinese',spec=['target_lang','_perform_translation'])
        engine._perform_translation.side_effect=RuntimeError('network unavailable')
        blocks=[TextBlock(text='はい',translation='original')]
        with self.assertRaises(RuntimeError):core.translate_reviewed(engine,blocks,None,'')
        self.assertEqual(engine._perform_translation.call_count,1)
        self.assertEqual(blocks[0].translation,'original')

    def test_structured_translation_and_copy(self):
        blocks=[TextBlock(text='はい')]
        class Stub:
            target_lang='Simplified Chinese'
            def _perform_translation(self,*args):return json.dumps({'blocks':{'block_0':{'translation':'是','status':'needs_review','notes':['指代不明']}},'terms':[{'source':'ホームラン','target':'本垒打'}],'summary':'测试摘要'})
        core.translate_reviewed(Stub(),blocks,None,'')
        clone=blocks[0].deep_copy()
        self.assertEqual(clone.yomi_status,'needs_review')
        self.assertEqual(clone.yomi_notes,['指代不明'])
        self.assertEqual(core.read_memory()['terms'][0]['status'],'proposed')
    def test_duplicate_and_invalid_confirmation(self):
        with self.assertRaises(ValueError):core.parse_response('{"blocks":{},"blocks":{}}',{})
        with self.assertRaises(ValueError):core.parse_response(json.dumps({'blocks':{'block_0':{'translation':'是','status':'verified','notes':[]}}}),{'block_0':'はい'})
    def test_pdf_import(self):
        p=Path(self.scratch.name)/'input.pdf'
        img=Image.new('RGB',(200,280),'white');img.save(p,save_all=True,append_images=[img])
        paths=self.window.file_handler.prepare_files([str(p)])
        self.assertEqual(len(paths),2)
        self.assertTrue(ensure_prepared_path_materialized(paths[0]))
        with Image.open(paths[0]) as image: self.assertGreater(image.width,0)
    def test_ui_edit_resets_confirmation(self):
        w=self.window
        w.image_files=['test-page.png'];w.curr_img_idx=0
        b=TextBlock(text_bbox=np.array([0,0,100,100]),text='はい',translation='是');b.yomi_status='verified';b.yomi_notes=[]
        w.blk_list=[b];w.refresh_review(force=True)
        w.review_table.item(0,1).setText('好的')
        self.assertEqual(b.translation,'好的');self.assertEqual(b.yomi_status,'proposed')
        self.assertEqual(len(core.read_memory()['reviews']),1)
        w.blk_list=[]

if __name__=='__main__':unittest.main(verbosity=2)


