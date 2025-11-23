import sys
import os
# Add the location of tidy.dll to the DLL search path.
# This is required for pytidylib to find the library on Windows.
if hasattr(os, 'add_dll_directory'):
    dll_path = os.path.dirname(os.path.abspath(__file__))
    os.add_dll_directory(dll_path)

import darkdetect
from lxml import etree
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit,
                               QPlainTextEdit, QPushButton, QSplitter, QFileDialog, QGroupBox, QMenu, QLabel)
from PySide6.QtGui import (QFont, QColor, QTextCharFormat, QTextCursor, QPainter, QIcon,
                           QKeySequence, QAction, QSyntaxHighlighter, QClipboard)
from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer
from saxonche import PySaxonProcessor
from pygments.lexers import XmlLexer
from pygments.styles import get_style_by_name
from pygments.token import Token

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Not bundled, running in a normal Python environment
        base_path = os.path.abspath(".")
    
    # When bundled, PyInstaller places the data files at the root.
    # The original path was 'src/main/python/icon.svg', so we just need the basename.
    if getattr(sys, 'frozen', False):
        return os.path.join(base_path, os.path.basename(relative_path))
        
    return os.path.join(base_path, relative_path)

class XmlHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.lexer = XmlLexer()
        self.styles = self.get_pygments_styles()

    def get_pygments_styles(self):
        styles = {}
        style_name = 'monokai' if darkdetect.theme() == "Dark" else 'default'
        style = get_style_by_name(style_name)
        for token, style_string in style.styles.items():
            fmt = QTextCharFormat()
            s = {'color': None, 'bold': False, 'italic': False, 'underline': False}
            for part in style_string.split():
                if part.startswith('#'):
                    s['color'] = part[1:]
                elif part == 'bold':
                    s['bold'] = True
                elif part == 'italic':
                    s['italic'] = True
                elif part == 'underline':
                    s['underline'] = True

            if s['color']:
                fmt.setForeground(QColor(f"#{s['color']}"))
            if s['bold']:
                fmt.setFontWeight(QFont.Bold)
            if s['italic']:
                fmt.setFontItalic(True)
            if s['underline']:
                fmt.setFontUnderline(True)
            styles[token] = fmt
        return styles

    def highlightBlock(self, text):
        # Use get_tokens_unprocessed to get start index of each token
        for index, token_type, value in self.lexer.get_tokens_unprocessed(text):
            length = len(value)
            style = self.styles.get(token_type)
            if style:
                self.setFormat(index, length, style)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    xpath_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.xpath_update_timer = QTimer(self)
        self.xpath_update_timer.setInterval(500)
        self.xpath_update_timer.setSingleShot(True)
        self.xpath_update_timer.timeout.connect(self._update_xpath)
        
        self.cursorPositionChanged.connect(self.xpath_update_timer.start)
        
        self.updateLineNumberAreaWidth(0)
        
        font = QFont("Consolas", 10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.highlighter = XmlHighlighter(self.document())
        self.highlightCurrentLine()

    def _update_xpath(self):
        try:
            text = self.toPlainText()
            if not text.strip():
                self.xpath_changed.emit("")
                return

            # Use a placeholder to preserve the &#10; entity
            placeholder = "___GEMINI_NEWLINE_PLACEHOLDER___"
            text_with_placeholder = text.replace("&#10;", placeholder)

            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(text_with_placeholder.encode('utf-8'), parser)
            
            tree = etree.ElementTree(root)

            cursor = self.textCursor()
            line_number = cursor.blockNumber() + 1

            element = None
            # This logic is non-functional without sourceline, but it prevents the app from crashing.
            for elem in root.iter():
                if hasattr(elem, 'sourceline') and elem.sourceline == line_number:
                    element = elem
                    break 

            if element is not None:
                xpath = tree.getpath(element)
                xpath = xpath.replace(placeholder, "&#10;")
                self.xpath_changed.emit(xpath)
            else:
                self.xpath_changed.emit("") # Silently fails, but doesn't crash

        except etree.XMLSyntaxError as e:
            self.xpath_changed.emit("Invalid XML")
            # Preserve error logging to console for future testing - necessary for Gemini.
            print(f"XPath Update Error (XML Syntax): {e}")
        except Exception as e:
            self.xpath_changed.emit("")
            # Preserve error logging to console for future testing - necessary for Gemini.
            print(f"XPath Update Error (General): {e}")

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        if darkdetect.theme() == "Dark":
            painter.fillRect(event.rect(), QColor("#2a2a2a"))
            pen_color = Qt.lightGray
        else:
            painter.fillRect(event.rect(), Qt.lightGray)
            pen_color = Qt.black

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(pen_color)
                painter.drawText(0, int(top), self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1
            
    def copy_xpath_to_clipboard(self):
        try:
            text = self.toPlainText()
            if not text.strip():
                return

            # Use a placeholder to preserve the &#10; entity
            placeholder = "___GEMINI_NEWLINE_PLACEHOLDER___"
            text_with_placeholder = text.replace("&#10;", placeholder)

            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(text_with_placeholder.encode('utf-8'), parser)
            
            tree = etree.ElementTree(root)

            cursor = self.textCursor()
            line_number = cursor.blockNumber() + 1

            element = None
            # This logic is non-functional without sourceline, but it prevents the app from crashing.
            for elem in root.iter():
                if hasattr(elem, 'sourceline') and elem.sourceline == line_number:
                    element = elem
                    break

            if element is not None:
                xpath = tree.getpath(element)
                xpath = xpath.replace(placeholder, "&#10;")
                clipboard = QApplication.clipboard()
                clipboard.setText(xpath)
                main_window = self.window()
                if hasattr(main_window, 'statusBar'):
                    main_window.statusBar().showMessage("XPath copied to clipboard.", 2000)
            else:
                main_window = self.window()
                if hasattr(main_window, 'statusBar'):
                    main_window.statusBar().showMessage("No element found at this line.", 3000)

        except etree.XMLSyntaxError as e:
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage(f"Could not copy XPath: Invalid XML - {e}", 5000)
            # Preserve error logging to console for future testing - necessary for Gemini.
            print(f"Copy XPath Error (XML Syntax): {e}")
        except Exception as e:
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage(f"An unexpected error occurred while copying XPath: {e}", 5000)
            # Preserve error logging to console for future testing - necessary for Gemini.
            print(f"Copy XPath Error (General): {e}")

    def show_context_menu(self, position):
        context_menu = QMenu(self)
        
        copy_xpath_action = context_menu.addAction("Copy XPath")
        copy_xpath_action.triggered.connect(self.copy_xpath_to_clipboard)
        
        if not self.isReadOnly():
            format_action = context_menu.addAction("Format")
            format_action.triggered.connect(self.pretty_print_xml)
            
        context_menu.exec(self.mapToGlobal(position))
            
    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            if darkdetect.theme() == "Dark":
                lineColor = QColor("#404040") 
            else:
                lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def pretty_print_xml(self):
        try:
            cursor = self.textCursor()
            original_pos = cursor.position()
            original_text = self.toPlainText()

            if not original_text.strip():
                return

            # Use a placeholder to preserve the &#10; entity
            placeholder = "___GEMINI_NEWLINE_PLACEHOLDER___"
            text_with_placeholder = original_text.replace("&#10;", placeholder)

            # Use lxml to parse and re-serialize with pretty printing
            parser = etree.XMLParser(remove_blank_text=True, recover=True)
            root = etree.fromstring(text_with_placeholder.encode('utf-8'), parser)

            # Use lxml's built-in pretty printing
            formatted_xml_with_placeholder = etree.tostring(root, pretty_print=True, encoding='unicode')

            # Restore the &#10; entity
            final_xml = formatted_xml_with_placeholder.replace(placeholder, "&#10;")

            if original_text.strip() != final_xml.strip():
                self.setPlainText(final_xml)
                self.document().setModified(True)

            cursor.setPosition(original_pos)
            self.setTextCursor(cursor)

            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage("Formatted successfully.", 2000)

        except etree.XMLSyntaxError as e:
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage(f"Formatting Error: Invalid XML - {e}", 5000)
        except Exception as e:
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage(f"An unexpected error occurred: {e}", 5000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XSLT Tester")
        self.setWindowIcon(QIcon(resource_path("src/main/python/icon.ico")))
        self.resize(1024, 768)
        
        self.xml_file_path = None
        self.xslt_file_path = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_bar_layout = QHBoxLayout()
        main_layout.addLayout(top_bar_layout)
        
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("&File")
        
        open_xml_action = QAction("Open XML", self)
        open_xml_action.triggered.connect(self.open_xml_file)
        file_menu.addAction(open_xml_action)

        open_xslt_action = QAction("Open XSLT", self)
        open_xslt_action.triggered.connect(self.open_xslt_file)
        file_menu.addAction(open_xslt_action)
        file_menu.addSeparator()

        self.save_xml_action = QAction("Save XML", self)
        self.save_xml_action.triggered.connect(self.save_xml)
        self.save_xml_action.setEnabled(False)
        file_menu.addAction(self.save_xml_action)
        
        self.save_as_xml_action = QAction("Save XML As...", self)
        self.save_as_xml_action.triggered.connect(self.save_xml_as)
        file_menu.addAction(self.save_as_xml_action)
        file_menu.addSeparator()

        self.save_xslt_action = QAction("Save XSLT", self)
        self.save_xslt_action.triggered.connect(self.save_xslt)
        self.save_xslt_action.setEnabled(False)
        file_menu.addAction(self.save_xslt_action)

        self.save_as_xslt_action = QAction("Save XSLT As...", self)
        self.save_as_xslt_action.triggered.connect(self.save_xslt_as)
        file_menu.addAction(self.save_as_xslt_action)
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        transform_button = QPushButton("Transform")
        transform_button.clicked.connect(self.transform)
        top_bar_layout.addWidget(transform_button)
        top_bar_layout.addStretch()

        main_splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(main_splitter)

        top_splitter = QSplitter(Qt.Horizontal)
        
        self.xml_group = QGroupBox("XML Input")
        xml_layout = QVBoxLayout()
        self.xml_editor = CodeEditor()
        xml_layout.addWidget(self.xml_editor)
        self.xml_group.setLayout(xml_layout)
        
        self.xslt_group = QGroupBox("XSLT Stylesheet")
        xslt_layout = QVBoxLayout()
        self.xslt_editor = CodeEditor()
        xslt_layout.addWidget(self.xslt_editor)
        self.xslt_group.setLayout(xslt_layout)

        top_splitter.addWidget(self.xml_group)
        top_splitter.addWidget(self.xslt_group)
        
        self.output_group = QGroupBox("Output")
        output_layout = QVBoxLayout()
        self.output_editor = CodeEditor()
        self.output_editor.setReadOnly(True)
        self.output_editor.setContextMenuPolicy(Qt.NoContextMenu)
        output_layout.addWidget(self.output_editor)
        self.output_group.setLayout(output_layout)

        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.output_group)
        
        top_splitter.setSizes([self.width() * 0.5, self.width() * 0.5])
        main_splitter.setSizes([self.height() * 0.6, self.height() * 0.4])
        
        self.xpath_label = QLabel("XPath: ")
        self.xpath_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.statusBar().addPermanentWidget(self.xpath_label)

        self.xml_editor.xpath_changed.connect(self.update_xpath_label)
        self.xslt_editor.xpath_changed.connect(self.update_xpath_label)
        self.output_editor.xpath_changed.connect(self.update_xpath_label)
        
        self.xml_editor.document().modificationChanged.connect(
            lambda modified: self.on_modification_changed(modified, self.xml_group, "XML Input", self.xml_file_path, self.save_xml_action)
        )
        self.xslt_editor.document().modificationChanged.connect(
            lambda modified: self.on_modification_changed(modified, self.xslt_group, "XSLT Stylesheet", self.xslt_file_path, self.save_xslt_action)
        )
        
        save_shortcut = QAction("Save Active", self)
        save_shortcut.setShortcut(QKeySequence.Save)
        save_shortcut.triggered.connect(self.save_active_editor)
        self.addAction(save_shortcut)

    def update_xpath_label(self, xpath):
        self.xpath_label.setText(f"XPath: {xpath}")

    def on_modification_changed(self, modified, group_box, base_title, file_path, save_action):
        title = base_title
        if file_path:
            title = os.path.basename(file_path)
        
        if modified:
            group_box.setTitle(f"{title} *")
        else:
            group_box.setTitle(title)
        
        save_action.setEnabled(modified)

    def open_xml_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open XML File", "", "XML Files (*.xml);;All Files (*)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.xml_editor.setPlainText(content)
                self.xml_file_path = filepath
                self.xml_editor.document().setModified(False)
                # Manually trigger the title update after loading a new file.
                self.on_modification_changed(False, self.xml_group, "XML Input", self.xml_file_path, self.save_xml_action)
            except Exception as e:
                self.statusBar().showMessage(f"Error opening XML file: {e}", 5000)

    def open_xslt_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open XSLT File", "", "XSLT Files (*.xsl *.xslt);;All Files (*)")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.xslt_editor.setPlainText(content)
                self.xslt_file_path = filepath
                self.xslt_editor.document().setModified(False)
                # Manually trigger the title update after loading a new file.
                self.on_modification_changed(False, self.xslt_group, "XSLT Stylesheet", self.xslt_file_path, self.save_xslt_action)
            except Exception as e:
                self.statusBar().showMessage(f"Error opening XSLT file: {e}", 5000)
    
    def _save_file(self, file_path, editor):
        try:
            content = editor.toPlainText()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            editor.document().setModified(False)
            self.statusBar().showMessage(f"Saved to {file_path}", 2000)
            return True
        except Exception as e:
            self.statusBar().showMessage(f"Error saving file: {e}", 5000)
            return False

    def save_xml(self):
        if self.xml_file_path:
            self._save_file(self.xml_file_path, self.xml_editor)
        else:
            self.save_xml_as()

    def save_xml_as(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save XML As", "", "XML Files (*.xml);;All Files (*)")
        if filepath:
            self.xml_file_path = filepath
            self._save_file(self.xml_file_path, self.xml_editor)

    def save_xslt(self):
        if self.xslt_file_path:
            self._save_file(self.xslt_file_path, self.xslt_editor)
        else:
            self.save_xslt_as()

    def save_xslt_as(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save XSLT As", "", "XSLT Files (*.xsl *.xslt);;All Files (*)")
        if filepath:
            self.xslt_file_path = filepath
            self._save_file(self.xslt_file_path, self.xslt_editor)

    def save_active_editor(self):
        if self.xml_editor.hasFocus():
            self.save_xml()
        elif self.xslt_editor.hasFocus():
            self.save_xslt()

    def transform(self):
        xml_input = self.xml_editor.toPlainText()
        xslt_input = self.xslt_editor.toPlainText()

        if not xml_input.strip() or not xslt_input.strip():
            self.statusBar().showMessage("XML and XSLT inputs cannot be empty.", 3000)
            return

        try:
            with PySaxonProcessor(license=False) as proc:
                xslt_proc = proc.new_xslt30_processor()
                document = proc.parse_xml(xml_text=xml_input)
                
                if not document:
                    self.statusBar().showMessage("Error parsing XML.", 5000)
                    self.output_editor.setPlainText("Error parsing XML.")
                    return
                    
                executable = xslt_proc.compile_stylesheet(stylesheet_text=xslt_input)
                output = executable.transform_to_string(xdm_node=document)
                
                self.output_editor.setPlainText(output)
                self.output_editor.pretty_print_xml()
                self.statusBar().showMessage("Transformation successful.", 2000)

        except Exception as e:
            self.output_editor.setPlainText(str(e))
            self.statusBar().showMessage("Transformation failed. See output for details.", 5000)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())