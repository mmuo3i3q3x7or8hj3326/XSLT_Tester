import sys
import os
# Add the location of tidy.dll to the DLL search path.
# This is required for pytidylib to find the library on Windows.
if hasattr(os, 'add_dll_directory'):
    dll_path = os.path.dirname(os.path.abspath(__file__))
    os.add_dll_directory(dll_path)

import darkdetect
import re
from io import BytesIO
from lxml import etree
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit,
                               QPlainTextEdit, QPushButton, QSplitter, QFileDialog, QGroupBox, QMenu, QLabel,
                               QLineEdit)
from PySide6.QtGui import (QFont, QColor, QTextCharFormat, QTextCursor, QPainter, QIcon,
                           QKeySequence, QAction, QSyntaxHighlighter, QClipboard, QTextDocument, QShortcut)
from PySide6.QtCore import Qt, QRect, QSize, Signal, QTimer, QRegularExpression
from saxonche import PySaxonProcessor
from pygments.lexers import XmlLexer
from pygments.styles import get_style_by_name
from pygments.token import Token

class SearchReplaceWidget(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.editor = editor
        self.setFocusProxy(self)
        self.setVisible(False)

        self.find_input = QLineEdit()
        self.replace_input = QLineEdit()
        self.find_input.setPlaceholderText("Find")
        self.replace_input.setPlaceholderText("Replace")

        self.close_button = QPushButton("X")
        
        self.case_sensitive_button = QPushButton("Aa")
        self.case_sensitive_button.setCheckable(True)
        self.case_sensitive_button.setToolTip("Case Sensitive")
        self.whole_word_button = QPushButton("W")
        self.whole_word_button.setCheckable(True)
        self.whole_word_button.setToolTip("Whole Words")
        self.regex_button = QPushButton(".*")
        self.regex_button.setCheckable(True)
        self.regex_button.setToolTip("Use Regular Expression")

        self.case_sensitive_button.toggled.connect(lambda checked: self.update_button_style(self.case_sensitive_button, checked))
        self.whole_word_button.toggled.connect(lambda checked: self.update_button_style(self.whole_word_button, checked))
        self.regex_button.toggled.connect(lambda checked: self.update_button_style(self.regex_button, checked))

        self.replace_button = QPushButton("Replace")
        self.replace_all_button = QPushButton("Replace All")

        self.close_button.clicked.connect(self.close_widget)
        self.close_button.setToolTip("Close (Esc)")
        self.find_input.textChanged.connect(self.editor.highlight_all_matches)
        self.find_input.returnPressed.connect(self.find_next)
        self.replace_input.returnPressed.connect(self.replace_current)
        self.replace_button.clicked.connect(self.replace_current)
        self.replace_all_button.clicked.connect(self.replace_all)

        #Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        find_layout = QHBoxLayout()
        find_layout.addWidget(self.find_input)
        find_layout.addWidget(self.case_sensitive_button)
        find_layout.addWidget(self.whole_word_button)
        find_layout.addWidget(self.regex_button)
        find_layout.addWidget(self.close_button)

        replace_layout = QHBoxLayout()
        replace_layout.addWidget(self.replace_input)
        replace_layout.addWidget(self.replace_button)
        replace_layout.addWidget(self.replace_all_button)

        main_layout.addLayout(find_layout)
        main_layout.addLayout(replace_layout)

        self.setLayout(main_layout)
        self.setStyleSheet("""
            SearchReplaceWidget {
                background-color: rgba(50, 50, 50, 0.9);
                border: 1px solid #555;
                border-radius: 5px;
            }
            QLineEdit {
                border: 1px solid #555;
                padding: 4px;
                background-color: #222;
                color: #ddd;
            }
            QPushButton {
                background-color: #555;
                color: #ddd;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)

    def close_widget(self):
        self.hide()
        self.editor.setFocus()
        
    def update_button_style(self, button, checked):
        if checked:
            button.setStyleSheet("""
                background-color: #007ACC;
                border: 1px solid #00568f;
                padding: 4px 8px;
                border-radius: 3px;
            """)
        else:
            button.setStyleSheet("""
                background-color: #555;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 3px;
            """)

    def show_widget(self, replace=False):
        if self.isVisible() and replace:
            self.replace_input.setVisible(True)
            self.replace_button.setVisible(True)
            self.replace_all_button.setVisible(True)
        else:
            self.setVisible(True)
            self.replace_input.setVisible(replace)
            self.replace_button.setVisible(replace)
            self.replace_all_button.setVisible(replace)
        
        self.find_input.setFocus()
        self.adjustSize()
        self.move(self.editor.viewport().width() - self.width() - 10, 10)

    def find_next(self):
        query = self.find_input.text()
        if self.regex_button.isChecked():
            options = QRegularExpression.NoPatternOption
            if not self.case_sensitive_button.isChecked():
                options |= QRegularExpression.CaseInsensitiveOption
            regex = QRegularExpression(query, options)
            if not regex.isValid(): return
            if not self.editor.find(regex):
                # Wrap search to the beginning
                self.editor.moveCursor(QTextCursor.Start)
                self.editor.find(regex)
        else:
            if not self.editor.find(query, self._get_find_flags()):
                # Wrap search to the beginning
                self.editor.moveCursor(QTextCursor.Start)
                self.editor.find(query, self._get_find_flags())

    def find_prev(self):
        query = self.find_input.text()
        find_flags = QTextDocument.FindBackward
        if self.regex_button.isChecked():
            options = QRegularExpression.NoPatternOption
            if not self.case_sensitive_button.isChecked():
                options |= QRegularExpression.CaseInsensitiveOption
            regex = QRegularExpression(query, options)
            if not regex.isValid(): return
            if not self.editor.find(regex, find_flags):
                # Wrap search to the end
                self.editor.moveCursor(QTextCursor.End)
                self.editor.find(regex, find_flags)
        else:
            find_flags |= self._get_find_flags()
            if not self.editor.find(query, find_flags):
                # Wrap search to the end
                self.editor.moveCursor(QTextCursor.End)
                self.editor.find(query, find_flags)

    def replace_current(self):
        if self.editor.textCursor().hasSelection():
            self.editor.textCursor().insertText(self.replace_input.text())
        self.find_next()

    def replace_all(self):
        self.editor.moveCursor(QTextCursor.Start)
        while self.editor.find(self.find_input.text(), self._get_find_flags()):
            self.editor.textCursor().insertText(self.replace_input.text())
            
    def _get_find_flags(self):
        flags = QTextDocument.FindFlags()
        if self.case_sensitive_button.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word_button.isChecked():
            flags |= QTextDocument.FindWholeWords
        return flags

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
        if self.document() and self.document().characterCount() > 2000000:
            return
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
        
        self.search_widget = SearchReplaceWidget(self)
        
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

    def keyPressEvent(self, event):
        if self.search_widget.isVisible() and self.search_widget.find_input.hasFocus():
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if event.modifiers() == Qt.ShiftModifier:
                    self.search_widget.find_prev()
                else:
                    self.search_widget.find_next()
                return
        super().keyPressEvent(event)
        
    def show_search_widget(self, replace=False):
        self.search_widget.show_widget(replace)

    def highlight_all_matches(self, text):
        extra_selections = []
        if not text:
            self.setExtraSelections(extra_selections)
            return

        document_cursor = QTextCursor(self.document())

        if self.search_widget.regex_button.isChecked():
            options = QRegularExpression.NoPatternOption
            if not self.search_widget.case_sensitive_button.isChecked():
                options |= QRegularExpression.CaseInsensitiveOption
            regex = QRegularExpression(text, options)
            if not regex.isValid():
                 self.setExtraSelections(extra_selections)
                 return
            
            match_count = 0
            while not document_cursor.isNull() and not document_cursor.atEnd():
                document_cursor = self.document().find(regex, document_cursor)
                if not document_cursor.isNull():
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(QColor("#FFA500")) # Orange highlight for regex
                    selection.cursor = document_cursor
                    extra_selections.append(selection)
                    match_count += 1
                    if match_count >= 1000:
                        break
                else:
                    break
        else:
            flags = self.search_widget._get_find_flags()
            match_count = 0
            while not document_cursor.isNull() and not document_cursor.atEnd():
                document_cursor = self.document().find(text, document_cursor, flags)
                if not document_cursor.isNull():
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(QColor("yellow"))
                    selection.cursor = document_cursor
                    extra_selections.append(selection)
                    match_count += 1
                    if match_count >= 1000:
                        break
                else:
                    break

        self.setExtraSelections(extra_selections)

    def get_detailed_xpath(self, element):
        root = element.getroottree().getroot()
        nsmap = {v: k for k, v in root.nsmap.items()}

        components = []
        child = element
        while child is not None:
            parent = child.getparent()

            qname = etree.QName(child)
            prefix = nsmap.get(qname.namespace)
            tag_name = qname.localname
            prefixed_tag = f"{prefix}:{tag_name}" if prefix else tag_name

            current_component = prefixed_tag
            predicate = ""

            if parent is not None: # Don't try to find siblings or attributes for the root element
                # Find siblings with the exact same prefixed tag name
                siblings_with_same_prefixed_tag = []
                for sib in parent:
                    sib_qname = etree.QName(sib)
                    sib_prefix = nsmap.get(sib_qname.namespace)
                    sib_prefixed_tag = f"{sib_prefix}:{sib_qname.localname}" if sib_prefix else sib_qname.localname
                    if sib_prefixed_tag == prefixed_tag:
                        siblings_with_same_prefixed_tag.append(sib)

                # Always try to find a strong identifying attribute predicate, if available and useful.
                identifying_attrs = ['id', 'ID', 'type', 'name', 'key']
                strong_identifying_attr_predicate = ""
                for attr_key, attr_value in child.attrib.items():
                    attr_qname = etree.QName(attr_key)
                    if attr_qname.localname in identifying_attrs:
                        # Check if this attribute makes it unique among siblings (if multiple siblings exist)
                        # Or if it's simply a strong identifier to make XPath more robust (even if unique by tag)
                        is_unique_by_this_attr = True
                        if len(siblings_with_same_prefixed_tag) > 1:
                            for sib in siblings_with_same_prefixed_tag:
                                if sib is not child and sib.get(attr_key) == attr_value:
                                    is_unique_by_this_attr = False
                                    break
                        
                        if is_unique_by_this_attr: # If unique or if only one sibling with this strong identifier
                            attr_prefix = nsmap.get(attr_qname.namespace)
                            attr_name = f"{attr_prefix}:{attr_qname.localname}" if attr_prefix else attr_qname.localname
                            strong_identifying_attr_predicate = f"[@{attr_name}='{attr_value}']"
                            break # Found a good identifying attribute, prioritize this one

                if strong_identifying_attr_predicate:
                    predicate = strong_identifying_attr_predicate
                elif len(siblings_with_same_prefixed_tag) > 1:
                    # If no strong identifying attribute or it's not unique by that, use index
                    idx = siblings_with_same_prefixed_tag.index(child) + 1
                    predicate = f"[{idx}]"
            
            current_component += predicate
            components.append(current_component)
            child = parent

        components.reverse()
        return '/' + '/'.join(components)

    def find_element_at_line(self, root, line_number):
        best_candidate = None
        for elem in root.iter():
            if hasattr(elem, 'sourceline') and elem.sourceline is not None:
                if elem.sourceline > line_number:
                    # Once we pass the target line, the last element seen is the best candidate
                    return best_candidate
                best_candidate = elem
        return best_candidate

    def _generate_xpath_at_cursor(self):
        try:
            if self.document() and self.document().characterCount() > 2000000:
                return "XPath disabled for large files (> 2000000 characters)"

            text = self.toPlainText()
            if not text.strip():
                return ""

            placeholder = "___GEMINI_NEWLINE_PLACEHOLDER___"
            text_with_placeholder = text.replace("&#10;", placeholder)

            # Use the 'recover' parser to handle potentially non-well-formed XML during editing
            parser = etree.XMLParser(recover=True)
            # Use BytesIO to handle encoding correctly
            root = etree.parse(BytesIO(text_with_placeholder.encode('utf-8')), parser).getroot()

            cursor = self.textCursor()
            line_number = cursor.blockNumber() + 1
            col_number = cursor.positionInBlock()

            element = self.find_element_at_line(root, line_number)
            if element is None:
                return ""

            xpath = self.get_detailed_xpath(element)

            cursor_line_text = cursor.block().text()
            # Regex to find attribute name and its value
            attr_regex = re.compile(r'([\w:-]+)\s*=\s*(["\'])(.*?)\2')
            for match in attr_regex.finditer(cursor_line_text):
                attr_name = match.group(1)
                # Span for the attribute name
                name_start, name_end = match.span(1)
                # Span for the attribute value (inside the quotes)
                val_start, val_end = match.span(3)

                # Check if cursor is on the name OR the value
                if (name_start <= col_number < name_end) or (val_start <= col_number < val_end):
                    xpath += f'/@{attr_name}'
                    break
            
            return xpath.replace(placeholder, "&#10;")

        except etree.XMLSyntaxError:
            # Re-raise to be caught by the calling function
            raise
        except Exception as e:
            # Log other unexpected errors
            print(f"XPath Generation Error (General): {e}")
            return ""

    def _update_xpath(self):
        try:
            xpath = self._generate_xpath_at_cursor()
            self.xpath_changed.emit(xpath)
        except etree.XMLSyntaxError:
            self.xpath_changed.emit("Invalid XML")
        except Exception as e:
            self.xpath_changed.emit("")
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
        self.search_widget.move(self.viewport().width() - self.search_widget.width() - 10, 10)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        if darkdetect.theme() == "Dark":
            painter.fillRect(event.rect(), QColor("#2a2a2a"))
            pen_color = Qt.lightGray
        else:
            painter.fillRect(event.rect(), QColor("#F0F0F0"))
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
            xpath = self._generate_xpath_at_cursor()
            if xpath:
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
            print(f"Copy XPath Error (XML Syntax): {e}")
        except Exception as e:
            main_window = self.window()
            if hasattr(main_window, 'statusBar'):
                main_window.statusBar().showMessage(f"An unexpected error occurred while copying XPath: {e}", 5000)
            print(f"Copy XPath Error (General): {e}")

    def show_context_menu(self, position):
        context_menu = QMenu(self)
        
        find_action = context_menu.addAction("Find...")
        find_action.triggered.connect(self.show_search_widget)
        
        replace_action = context_menu.addAction("Replace...")
        replace_action.triggered.connect(lambda: self.show_search_widget(replace=True))

        context_menu.addSeparator()
        
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
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
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

        edit_menu = self.menu_bar.addMenu("&Edit")
        self.find_action = QAction("Find...", self)
        self.replace_action = QAction("Replace...", self)
        self.copy_xpath_action = QAction("Copy XPath", self)
        self.format_action = QAction("Format", self)
        
        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.replace_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.copy_xpath_action)
        edit_menu.addAction(self.format_action)

        self.find_action.triggered.connect(self.find_in_active_editor)
        self.replace_action.triggered.connect(self.replace_in_active_editor)
        self.copy_xpath_action.triggered.connect(self.copy_xpath_in_active_editor)
        self.format_action.triggered.connect(self.format_in_active_editor)

        QApplication.instance().focusChanged.connect(self.handle_focus_change)
        self.handle_focus_change(None, None) # Set initial state

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

        find_action = QAction("Find", self)
        find_action.setShortcut(QKeySequence.Find)
        find_action.triggered.connect(self.show_search_widget_for_active_editor)
        self.addAction(find_action)

        replace_action = QAction("Replace", self)
        replace_action.setShortcut(QKeySequence.Replace)
        replace_action.triggered.connect(lambda: self.show_search_widget_for_active_editor(replace=True))
        self.addAction(replace_action)

    def _get_active_editor(self):
        widget = QApplication.focusWidget()
        if isinstance(widget, CodeEditor):
            return widget
        # Check parent if the viewport or another child widget has focus
        if isinstance(widget, QWidget) and isinstance(widget.parent(), CodeEditor):
            return widget.parent()
        return None

    def find_in_active_editor(self):
        editor = self._get_active_editor()
        if editor:
            editor.show_search_widget()

    def replace_in_active_editor(self):
        editor = self._get_active_editor()
        if editor:
            editor.show_search_widget(replace=True)

    def copy_xpath_in_active_editor(self):
        editor = self._get_active_editor()
        if editor:
            editor.copy_xpath_to_clipboard()

    def format_in_active_editor(self):
        editor = self._get_active_editor()
        if editor and not editor.isReadOnly():
            editor.pretty_print_xml()

    def handle_focus_change(self, old_widget, new_widget):
        active_editor = self._get_active_editor()
        is_editable = bool(active_editor and not active_editor.isReadOnly())

        self.find_action.setEnabled(bool(active_editor))
        self.replace_action.setEnabled(bool(active_editor))
        self.copy_xpath_action.setEnabled(bool(active_editor))
        self.format_action.setEnabled(is_editable)

    def show_search_widget_for_active_editor(self, replace=False):
        active_editor = self.focusWidget()
        if isinstance(active_editor, CodeEditor):
            search_widget = active_editor.search_widget
            if search_widget.isVisible() and search_widget.replace_input.isVisible():
                if replace:
                    if search_widget.replace_input.hasFocus():
                        search_widget.find_input.setFocus()
                    else:
                        search_widget.replace_input.setFocus()
                else:
                    search_widget.find_input.setFocus()
            else:
                active_editor.show_search_widget(replace)

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