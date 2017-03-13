import enum

from PyQt5 import QtGui, QtWidgets, QtCore

from vqt.main import *
from vqt.common import *

import envi.memcanvas as e_memcanvas


class ContentTagsEnum(enum.IntEnum):
    """All known tags that can be recognized and highlighted by this canvas
    """
    CURRENT_LINE = -2
    DEFAULT = -1
    VA = 0
    NAME = 1
    XREFS = 2
    COMMENT = 3
    LOCATION = 4
    REGISTER = 5
    MNEMONIC = 6
    UNDEFINED = 7  # raw bytes usually


defaultCanvasColors = {
    # tag: (foreground, backgroun)
    ContentTagsEnum.CURRENT_LINE: ('#000000', '#1C2833'),
    ContentTagsEnum.DEFAULT: ('#58D68D', '#000000'),

    ContentTagsEnum.VA: ('#7FB3D5', '#000000'),
    ContentTagsEnum.NAME: ('#D0D3D4', '#000000'),
    ContentTagsEnum.XREFS: ('#AED6F1', '#000000'),
    ContentTagsEnum.COMMENT: ('#28B463', '#000000'),
    ContentTagsEnum.LOCATION: ('#AED6F1', '#000000'),
    ContentTagsEnum.REGISTER: ('#AF7AC5', '#000000'),
    ContentTagsEnum.MNEMONIC: ('#F1C40F', '#000000'),
    ContentTagsEnum.UNDEFINED: ('#D0D3D4', '#000000')
}


class VivCanvasColors:
    def __init__(self, theme: dict = defaultCanvasColors):
        self.theme = theme
        self._formats = dict()
        self._colors = dict()
        self._prepareTheme()

    def _prepareTheme(self):
        for tag, fg_bg in self.theme.items():
            fg = QtGui.QColor(fg_bg[0])
            bg = QtGui.QColor(fg_bg[1])
            self._colors[tag] = (fg, bg)

            f = QtGui.QTextCharFormat()
            f.setForeground(fg)
            f.setBackground(bg)
            self._formats[tag] = f

    def changeTheme(self, theme: dict):
        self.theme = theme
        self._formats.clear()
        self._colors.clear()
        self._prepareTheme()

    def getFormat(self, tag: ContentTagsEnum) -> QtGui.QTextCharFormat:
        return self._formats.get(tag)

    def getColors(self, tag: ContentTagsEnum) -> tuple:  # QtGui.QColor
        return self._colors.get(tag)


class VQMemoryCanvas(e_memcanvas.MemoryCanvas, QtWidgets.QPlainTextEdit):
    """A widget based implementation of a memory canvas.
    Usually what you see and use in vivisect most of the time.
    """

    def __init__(self, mem, syms=None, parent=None):
        e_memcanvas.MemoryCanvas.__init__(self, mem, syms=syms)
        QtWidgets.QPlainTextEdit.__init__(self, parent=parent)

        self.setReadOnly(True)
        self.cursorPositionChanged.connect(self._cursorChanged)

        self._highlighter = VivCanvasColors()
        self.setCurrentCharFormat(self._highlighter.getFormat(ContentTagsEnum.DEFAULT))
        self._cur_line_bg_color = self._highlighter.getColors(ContentTagsEnum.CURRENT_LINE)[1]

        self._canv_cache = None
        self._canv_curva = None
        self._canv_rend_middle = False

        self._va_to_line = dict()
        self._line_to_va = dict()

        # Allow our parent to handle these...
        self.setAcceptDrops(False)

    def _clearInternals(self):
        self._va_to_line.clear()
        self._line_to_va.clear()
        self._canv_curva = None
        self._canv_cache = None

    def _cursorPositionToVa(self):
        # using the internal structures translate the cursor position to va
        cur = self.textCursor()
        va_line = cur.block().position()
        va = self._line_to_va.get(va_line)

        if va is None:
            # the cursor might be positioned in a multi line va such as a function
            # we will do an exhaust search in the rendered vas
            for _va, (pos_start, pos_end) in self._va_to_line.items():
                if pos_end is None:
                    pos_end = pos_start
                if pos_start <= va_line <= pos_end:
                    va = _va
                    break
        return va

    def _cursorChanged(self):
        # the cursor position has changed
        # 1) figure out the new va
        self._canv_curva = self._cursorPositionToVa()
        # 2) highlight the line
        self._highlightCurrentLine()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            self.setReadOnly(True)
            d = event.angleDelta()
            if d.y() > 0:
                self.zoomIn(2)
            else:
                self.zoomOut(2)
            event.accept()
            self.setReadOnly(False)
            return

        try:
            bar = self.verticalScrollBar()
            sbcur = bar.value()
            sbmin = bar.minimum()
            sbmax = bar.maximum()

            if sbcur == sbmax:

                lastva, lastsize = self._canv_rendvas[-1]
                mapva, mapsize, mperm, mfname = self.vw.getMemoryMap(lastva)
                sizeremain = (mapva + mapsize) - (lastva + lastsize)
                if sizeremain:
                    self.renderMemoryAppend(min(sizeremain, 128))

            elif sbcur == sbmin:
                firstva, firstsize = self._canv_rendvas[0]
                mapva, mapsize, mperm, mfname = self.vw.getMemoryMap(firstva)
                sizeremain = firstva - mapva
                if sizeremain:
                    self.renderMemoryPrepend(min(sizeremain, 128))
        except:
            pass

        return super(VQMemoryCanvas, self).wheelEvent(event)

    # @idlethread
    def renderMemory(self, va, size, rend=None):

        if self._canv_rend_middle:
            vmap = self.mem.getMemoryMap(va)
            if vmap is None:
                raise Exception('Invalid Address:%s' % hex(va))

            origva = va
            va, szdiff = self._loc_helper(max(va - size, vmap[0]))
            size += size + szdiff

        ret = super(VQMemoryCanvas, self).renderMemory(va, size, rend=rend)

        if self._canv_rend_middle:
            self._putCursorAtVa(origva)

        return ret

    def _putCursorAtVa(self, va):
        self._canv_curva = va
        start_pos = self._va_to_line[va][0]
        end_pos = self._va_to_line[va][1]-1
        cursor = self.textCursor()
        # cursor.setPosition(start_pos, QtGui.QTextCursor.MoveAnchor)
        cursor.setPosition(end_pos, QtGui.QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)
        self._highlightCurrentLine()
        self.centerCursor()

    def _highlightCurrentLine(self):
        high_line = QtWidgets.QTextEdit.ExtraSelection()
        high_line.format.setBackground(self._cur_line_bg_color)
        high_line.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)

        high_line.cursor = self.textCursor()
        high_line.cursor.clearSelection()
        self.setExtraSelections([high_line])

    #####################################################
    def _beginRenderMemory(self, va, size, rend):
        self._canv_cache = ''

    def _endRenderMemory(self, va, size, rend):
        self._canv_cache = None

    #####################################################
    # basic sequential rendering
    def _beginRenderVa(self, va):
        block_pos = self.textCursor().position()
        self._va_to_line[va] = [block_pos, None]
        self._line_to_va[block_pos] = va

    def _endRenderVa(self, va, size):
        self._va_to_line[va][1] = self.textCursor().position()

    #####################################################
    # when something has changed and needs update
    def _beginUpdateVas(self, valist: list):
        self._canv_cache = ''
        # mark the lines and delete them valist = [(va, size), ...]
        start_va = valist[0][0]
        end_va = valist[-1][0]

        try:
            s_va_start_pos, s_va_end_pos = self._va_to_line[start_va]
            e_va_start_pos, e_va_end_pos = self._va_to_line[end_va]

            tcur = self.textCursor()
            tcur.setPosition(s_va_start_pos, QtGui.QTextCursor.MoveAnchor)
            tcur.setPosition(e_va_end_pos, QtGui.QTextCursor.KeepAnchor)
            tcur.deleteChar()

            # now remove the old info from the internal state holders
            for va, size in valist:
                start_pos, end_pos = self._va_to_line[va]
                self._line_to_va.pop(start_pos)
                self._va_to_line.pop(va)

            self.setTextCursor(tcur)
        except Exception as e:
            traceback.print_exc()

    def _endUpdateVas(self):
        self._canv_cache = None

    #####################################################
    def _beginRenderPrepend(self):
        self._canv_cache = ''

    def _endRenderPrepend(self):
        self._canv_cache = None

    #####################################################
    def _beginRenderAppend(self):
        self._canv_cache = ''

    def _endRenderAppend(self):
        self._canv_cache = None

    #####################################################
    def getNameTag(self, name, typename='name'):
        """ The render class will call these xxxTag methods when he wants to add a text representation of a
        specific data: registers, mnemonics etc. We basically have to return some kind of identifier that will
        later be given back to us as a parameter in addText() so that we know how to handle this text.
        Very useful for highlighting etc.

        :param name: basically the text that will be added
        :param typename: what kind it is.
        :return: object
        """
        if typename == 'mnemonic':
            return ContentTagsEnum.MNEMONIC
        elif typename == 'registers':
            return ContentTagsEnum.REGISTER
        elif typename == 'undefined':
            return ContentTagsEnum.UNDEFINED
        else:
            return ContentTagsEnum.NAME

    def getTag(self, typename):
        if typename == 'comment':
            return ContentTagsEnum.COMMENT
        elif typename == 'xrefs':
            return ContentTagsEnum.XREFS
        elif typename == 'location':
            return ContentTagsEnum.LOCATION
        print("UNKNOWN TAG:", typename)
        return None

    def getVaTag(self, va):
        return ContentTagsEnum.VA

    @idlethread
    def _appendInside(self, text, highlight=None):
        if highlight is not None:
            cformat = self.currentCharFormat()
            self.setCurrentCharFormat(highlight)
            self.insertPlainText(text)
            self.setCurrentCharFormat(cformat)
        else:
            self.insertPlainText(text)

        if self._canv_scrolled is True:
            self.moveCursor(QtGui.QTextCursor.End)
        else:
            self._highlightCurrentLine()

    def addText(self, text, tag=None):
        h = self._highlighter.getFormat(tag)
        self._appendInside(text, h)

    @idlethreadsync
    def clearCanvas(self):
        self.clear()
        self._clearInternals()

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        self.initMemWindowMenu(self._canv_curva, menu)

        viewmenu = menu.addMenu('view   ')
        viewmenu.addAction("Save frame to HTML", ACT(self._menuSaveToHtml))
        menu.exec_(event.globalPos())

    # def initMemWindowMenu(self, va, menu):
    #     initMemSendtoMenu('0x%.8x' % va, menu)
    #     super(VQMemoryCanvas, self).initMemWindowMenu(va, menu)

    def _menuSaveToHtml(self):
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save As HTML...')


def getNavTargetNames():
    """
    Returns a list of Memory View names.
    Populated by vqt in a separate thread, thus is time-sensitive.  If the
    list is accessed too quickly, some valid names may not yet be inserted.
    """
    ret = []
    vqtevent('envi:nav:getnames', ret)
    return ret


def initMemSendtoMenu(expr, menu):
    for name in set(getNavTargetNames()):
        args = (name, expr, None)
        menu.addAction('sendto: %s' % name, ACT(vqtevent, 'envi:nav:expr', args))
