import enum
import threading

from PyQt5 import QtGui, QtWidgets, QtCore

from vqt.main import *
from vqt.common import *

import envi.memcanvas as e_memcanvas


class ContentTagsEnum(enum.IntEnum):
    """All known tags that can be recognized and highlighted by this canvas
    """
    HIGHLIGHT = -3
    CURRENT_LINE = -2
    DEFAULT = -1
    VA = 0
    NAME = 1
    XREFS = 2
    STRING = 3
    COMMENT = 4
    LOCATION = 5
    REGISTER = 6
    MNEMONIC = 7
    UNDEFINED = 8  # raw bytes usually


defaultCanvasColors = {
    # tag: (foreground, backgroun)
    ContentTagsEnum.HIGHLIGHT: ("#000000", '#515A5A'),
    ContentTagsEnum.CURRENT_LINE: ('#000000', '#1C2833'),
    ContentTagsEnum.DEFAULT: ('#58D68D', '#000000'),

    ContentTagsEnum.VA: ('#7FB3D5', '#000000'),
    ContentTagsEnum.NAME: ('#D0D3D4', '#000000'),
    ContentTagsEnum.XREFS: ('#AED6F1', '#000000'),
    ContentTagsEnum.STRING: ('#58D68D', '#000000'),
    ContentTagsEnum.COMMENT: ('#28B463', '#000000'),
    ContentTagsEnum.LOCATION: ('#AED6F1', '#000000'),
    ContentTagsEnum.REGISTER: ('#AF7AC5', '#000000'),
    ContentTagsEnum.MNEMONIC: ('#F1C40F', '#000000'),
    ContentTagsEnum.UNDEFINED: ('#D0D3D4', '#000000')
}


class VivTextProperties(enum.IntEnum):
    vivTag = 1
    vivValue = 2


class VivTextBlockUserData(QtGui.QTextBlockUserData):
    def __init__(self, va: int, *args, **kwargs):
        super(VivTextBlockUserData, self).__init__(*args, **kwargs)
        self.va = va


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
        if tag not in self._colors:
            return None
        fg, bg = self._colors[tag]
        f = QtGui.QTextCharFormat()
        f.setForeground(fg)
        f.setBackground(bg)
        f.setProperty(VivTextProperties.vivTag, tag)
        return f

    def getColors(self, tag: ContentTagsEnum) -> tuple:  # QtGui.QColor
        return self._colors.get(tag)


class VQMemoryCanvas(e_memcanvas.MemoryCanvas, QtWidgets.QPlainTextEdit):
    """A widget based implementation of a memory canvas.
    Usually what you see and use in vivisect most of the time.
    """

    # in case of a fixed canvas and the user wants to go up/down this signal gets emit
    # with the next virtual address that is wanted
    leavesFixedScope = QtCore.pyqtSignal(int)

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
        self._do_heavy_highlight = False

        # keep track of highlighted blocks
        self._high_blocks = dict()
        self._high_bg_color = self._highlighter.getColors(ContentTagsEnum.HIGHLIGHT)[1]
        self._high_bg = QtGui.QBrush(self._high_bg_color)

        # Allow our parent to handle these...
        self.setAcceptDrops(False)

        # in case we want this canvas to display only a fixed amount of data at any time
        # useful for the function graph where one canvas renders one basic block of code etc.
        self._fixed_location = False
        # also in such cases we would like to know when the rendering of the given fixed region is done
        # because this rendering is done asynchronously in another thread
        self._render_counter = 0
        self._render_counter_lock = threading.Lock()

        self._max_text_width = 0
        self._cur_line_width = 0
        self._lines_height = 0

    def setFixedLocation(self, on: bool):
        self._fixed_location = on

    def isFixedLocationRenderingComplete(self) -> bool:
        return self._render_counter == 0

    def getBestDimensions(self):
        matrix = self.fontMetrics()
        r = QtCore.QRect(0, 0, 0, 0)
        rect = matrix.boundingRect(r, QtCore.Qt.AlignLeft, self.toPlainText())
        # width = matrix.maxWidth() * self._max_text_width
        # height = matrix.capHeight() * self._lines_height
        w = rect.width()
        w += w/10
        h = rect.height()
        h += h/5
        return w, h

    def _clearInternals(self):
        self._canv_curva = None
        self._canv_cache = None

    def _getBlockForVa(self, va):
        doc = self.document()

        fblock = doc.begin()
        lblock = doc.end()

        iblock = fblock
        while iblock != lblock:
            if self._getVaForBlock(iblock) == va:
                return iblock
            iblock = iblock.next()

        if self._getVaForBlock(iblock) == va:
            return iblock

        return None

    def _getVaForBlock(self, block: QtGui.QTextBlock):
        for tformatrange in block.textFormats():
            tag = tformatrange.format.property(VivTextProperties.vivTag)
            if tag is ContentTagsEnum.VA:
                return tformatrange.format.property(VivTextProperties.vivValue)
        return None

    def _cursorPositionToVa(self):
        cur = self.textCursor()
        return self._getVaForBlock(cur.block())

    def _cursorChanged(self):
        self._canv_curva = self._cursorPositionToVa()
        self._highlightCurrentLine()

    def keyPressEvent(self, ev: QtGui.QKeyEvent):
        ev.ignore()

    def keyReleaseEvent(self, ev: QtGui.QKeyEvent):
        ev.ignore()

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        self._do_heavy_highlight = True
        self._highlightClear()
        super(VQMemoryCanvas, self).mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev: QtGui.QMouseEvent):
        # super(VQMemoryCanvas, self).mouseDoubleClickEvent(ev)

        t = self.cursorForPosition(ev.pos())
        cf = t.charFormat()
        tag = cf.property(VivTextProperties.vivTag)
        val = cf.property(VivTextProperties.vivValue)

        if tag is ContentTagsEnum.VA:
            self.gotoVa(val)
        else:
            if self._hasHighligtedTags() is True:
                self._highlightClear()
            self._highlightTag(tag, val)

    def _highlightTag(self, tag, val):
        doc = self.document()
        fblock = doc.firstBlock()
        lblock = doc.lastBlock()

        iblock = fblock
        while iblock != lblock:
            text_formats = iblock.textFormats()
            for tf in text_formats:
                cf = tf.format
                btag = cf.property(VivTextProperties.vivTag)
                bval = cf.property(VivTextProperties.vivValue)

                if btag == tag and bval == val:
                    # save the original background
                    ipos = iblock.position() + tf.start
                    lpos = ipos + tf.length
                    self._high_blocks[ipos] = lpos, btag, bval

                    cf.setBackground(self._high_bg)
                    text_cur = self.textCursor()
                    text_cur.setPosition(ipos, QtGui.QTextCursor.MoveAnchor)
                    text_cur.setPosition(ipos + tf.length, QtGui.QTextCursor.KeepAnchor)
                    text_cur.setCharFormat(cf)
            iblock = iblock.next()

    def _hasHighligtedTags(self):
        return len(self._high_blocks) > 0

    def _highlightClear(self):
        if len(self._high_blocks) == 0:
            return

        tcur = self.textCursor()
        for ipos, ituple in self._high_blocks.items():
            lpos, btag, bval = ituple

            tcur.setPosition(ipos, QtGui.QTextCursor.MoveAnchor)
            tcur.setPosition(lpos, QtGui.QTextCursor.KeepAnchor)
            h = self._highlighter.getFormat(btag)
            h.setProperty(VivTextProperties.vivValue, bval)
            tcur.setCharFormat(h)
        self._high_blocks.clear()

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

        bar = self.verticalScrollBar()
        sbcur = bar.value()
        sbmin = bar.minimum()
        sbmax = bar.maximum()

        if sbcur == sbmax:
            self._try_Prefetch(forward=True)
        elif sbcur == sbmin:
            self._try_Prefetch(forward=False)

        ret = super(VQMemoryCanvas, self).wheelEvent(event)
        return ret

    def _try_Prefetch(self, forward: bool):
        # try to prefetch and render data inside the canvas
        # if forward is True we go forward otherwise backwards.

        if self._fixed_location is True:
            # if the canvas has to render only this location don't prefetch
            return

        try:

            if forward is True:
                lastva, lastsize = self._canv_rendvas[-1]
                mapva, mapsize, mperm, mfname = self.mem.getMemoryMap(lastva)
                add_size = (mapva + mapsize) - (lastva + lastsize)
                add_size = min(add_size, 128)
                if add_size:
                    o_va = self.__proper_va_offset(lastva, add_size)
                    self.renderMemoryAppend(o_va - lastva)
            else:
                firstva, firstsize = self._canv_rendvas[0]
                mapva, mapsize, mperm, mfname = self.mem.getMemoryMap(firstva)
                add_size = firstva - mapva
                add_size = min(add_size, 128)
                if add_size:
                    o_va = self.__proper_va_offset(firstva, -add_size)
                    self.renderMemoryPrepend(firstva - o_va)
        except IndexError as e:
            pass
        except Exception as e:
            traceback.print_exc()

    def __proper_va_offset(self, va: int, offset: int) -> int:
        # PROPERLY (taking care of locations) seek at least offset bytes forwards of backwards
        # if the offset lends inside a location boundaries it will round the return VA to point
        # to the start of the location.
        targetva = va + offset
        nextva = va

        if offset > 0:
            while nextva < targetva:
                loc = self.vw.getLocation(nextva)
                if loc is None:
                    loc = (nextva, 1, None, None)
                nextva = loc[0] + loc[1]
        else:
            while nextva > targetva:
                loc = self.vw.getPrevLocation(nextva)
                if loc is None:
                    loc = (nextva - 1, 1, None, None)
                nextva = loc[0]

        return nextva

    def gotoNext(self):
        if not self._canv_curva:
            return
        nextva = self.__proper_va_offset(self._canv_curva, 1)

        if self._canv_beginva <= nextva < self._canv_endva:
            self._putCursorAtVa(nextva)
        else:
            if self._fixed_location is True:
                self.leavesFixedScope.emit(nextva)
                return
            self._try_Prefetch(True)

    def gotoPrev(self):
        if not self._canv_curva:
            return
        nextva = self.__proper_va_offset(self._canv_curva, -1)

        if self._canv_beginva <= nextva < self._canv_endva:
            self._putCursorAtVa(nextva)
        else:
            if self._fixed_location is True:
                self.leavesFixedScope.emit(nextva)
                return
            self._try_Prefetch(False)

    def gotoVa(self, va):
        if self._canv_beginva < va < self._canv_endva:
            self._putCursorAtVa(va)
        else:
            if self._fixed_location is False:
                self.renderMemory(va, 256)

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

    def vivColorMap(self, event, einfo):
        self.applyColorMap(einfo)

    def applyColorMap(self, cmap: dict):
        pass
        # for va, color in cmap.items():
        #     pass

    def _putCursorAtVa(self, va):
        self._canv_curva = va
        block = self._getBlockForVa(va)
        cursor = self.textCursor()
        cursor.setPosition(block.position(), QtGui.QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)

        self._highlightCurrentLine()
        self.centerCursor()

    def _highlightCurrentLine(self):
        # ebahti zora!
        extra_selected = list()

        tc = self.textCursor()
        cblock = tc.block()
        _va = self._getVaForBlock(cblock)

        if self._do_heavy_highlight is True:
            cblock = self._getBlockForVa(_va)
            tc = QtGui.QTextCursor(cblock)
            self._do_heavy_highlight = False

        iblock = cblock
        eblock = self.document().end()
        cnt = 0

        while _va is not None and _va == self._getVaForBlock(iblock) and iblock != eblock:
            tc.movePosition(QtGui.QTextCursor.StartOfBlock, QtGui.QTextCursor.MoveAnchor)

            high_line = QtWidgets.QTextEdit.ExtraSelection()
            high_line.format.setBackground(self._cur_line_bg_color)
            high_line.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            high_line.cursor = tc
            high_line.cursor.clearSelection()
            extra_selected.append(high_line)

            iblock = iblock.next()
            tc.movePosition(QtGui.QTextCursor.NextBlock, QtGui.QTextCursor.MoveAnchor)

        self.setExtraSelections(extra_selected)

    #####################################################
    def _beginRenderMemory(self, va, size, rend):
        self._canv_cache = ''
        if self._fixed_location is True:
            # in this case we want to track the dimensions
            self._max_text_width = 0

        self._rendering_complete = False
        # self._beginRenderVa(va)

    def _endRenderMemory(self, va, size, rend):
        self._canv_cache = None

    #####################################################
    # basic sequential rendering
    def _beginRenderVa(self, va):
        self._canv_curva = va
        self._cur_line_width = 0

    def _endRenderVa(self, va, size):
        if self._fixed_location is True:
            self._lines_height += 1
            if self._cur_line_width > self._max_text_width:
                self._max_text_width = self._cur_line_width

    #####################################################
    # when something has changed and needs update
    def _beginUpdateVas(self, valist: list):
        self._canv_cache = ''
        # mark the lines and delete them valist = [(va, size), ...]
        start_va = valist[0][0]
        end_va = valist[-1][0]

        try:
            sblock = self._getBlockForVa(start_va)
            eblock = self._getBlockForVa(end_va)

            spos = sblock.position()
            epos = eblock.position() + eblock.length()

            tcur = self.textCursor()
            tcur.setPosition(spos, QtGui.QTextCursor.MoveAnchor)
            tcur.setPosition(epos, QtGui.QTextCursor.KeepAnchor)
            tcur.deleteChar()
            # self.setTextCursor(tcur)
        except Exception as e:
            traceback.print_exc()
            self.renderMemory(start_va, 256)

    def _endUpdateVas(self):
        self._canv_cache = None

    #####################################################
    def _beginRenderPrepend(self):
        self._canv_cache = ''
        fblock = self.document().firstBlock()
        tcur = self.textCursor()
        tcur.setPosition(fblock.position(), QtGui.QTextCursor.MoveAnchor)
        self.setTextCursor(tcur)

    def _endRenderPrepend(self):
        self._canv_cache = None

    #####################################################
    def _beginRenderAppend(self):
        self._canv_cache = ''
        lblock = self.document().lastBlock()
        lpos = lblock.position()
        tcur = self.textCursor()
        tcur.setPosition(lpos, QtGui.QTextCursor.MoveAnchor)
        self.setTextCursor(tcur)

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
        # ugly but much faster than any getattr or __members__ magic!
        if typename == 'mnemonic':
            return ContentTagsEnum.MNEMONIC, name
        elif typename == 'registers':
            return ContentTagsEnum.REGISTER, name
        elif typename == 'undefined':
            return ContentTagsEnum.UNDEFINED, name
        else:
            return ContentTagsEnum.NAME, name

    def getTag(self, typename):
        # ugly but much faster than any getattr or __members__ magic!
        if typename == 'comment':
            return ContentTagsEnum.COMMENT, self._canv_curva
        elif typename == 'xrefs':
            return ContentTagsEnum.XREFS, self._canv_curva
        elif typename == 'string':
            return ContentTagsEnum.STRING, self._canv_curva
        elif typename == 'location':
            return ContentTagsEnum.LOCATION, self._canv_curva
        print("UNKNOWN TAG:", typename)
        return None

    def getVaTag(self, va):
        return ContentTagsEnum.VA, va

    @idlethread
    def _appendInside(self, text, highlight=None):
        with self._render_counter_lock:
            self._render_counter -= 1

        if highlight is not None:
            cformat = self.currentCharFormat()
            self.setCurrentCharFormat(highlight)
            self.insertPlainText(text)
            self.setCurrentCharFormat(cformat)
        else:
            self.insertPlainText(text)

        if self._canv_scrolled is True:
            self.moveCursor(QtGui.QTextCursor.End)

    def addText(self, text, tag=None):
        if tag is not None:
            _tag, extra = tag
            h = self._highlighter.getFormat(_tag)
            h.setProperty(VivTextProperties.vivValue, extra)
        else:
            h = self._highlighter.getFormat(tag)

        with self._render_counter_lock:
            self._render_counter += 1

        self._cur_line_width += len(text)
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

    def _menuSaveToHtml(self):
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save As HTML...')[0]


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
