import enum

from PyQt5 import QtGui, QtWidgets

from vqt.main import *
from vqt.common import *

import envi.memcanvas as e_memcanvas


class ContentTagsEnum(enum.IntEnum):
    """All known tags that can be recognized and highlighted by this canvas
    """
    VA = 0
    NAME = 1
    XREFS = 2
    COMMENT = 3
    LOCATION = 4
    REGISTER = 5

defaultCanvasColors = {
    # tag: (foreground, backgroun)
    ContentTagsEnum.VA: ('#0f0fff', '#000000'),
    ContentTagsEnum.NAME: ('#00ff00', '#000000'),
    ContentTagsEnum.XREFS: ('#ff0000', '#000000'),
    ContentTagsEnum.COMMENT: ('#f0f0f0', '#000000'),
    ContentTagsEnum.LOCATION: ('#00aaff', '#000000')
}


class VivCanvasColors:
    def __init__(self, theme: dict = defaultCanvasColors):
        self.theme = theme
        self._formats = dict()
        self._prepareTheme()

    def _prepareTheme(self):
        for tag, fg_bg in self.theme.items():
            f = QtGui.QTextCharFormat()
            f.setForeground(QtGui.QColor(fg_bg[0]))
            f.setBackground(QtGui.QColor(fg_bg[1]))
            self._formats[tag] = f

    def changeTheme(self, theme: dict):
        self.theme = theme
        self._formats.clear()
        self._prepareTheme()

    def getFormat(self, tag: ContentTagsEnum) -> QtGui.QTextCharFormat:
        return self._formats.get(tag)


class VQMemoryCanvas(e_memcanvas.MemoryCanvas, QtWidgets.QPlainTextEdit):
    """A widget based implementation of a memory canvas.
    Usually what you see and use in vivisect most of the time.
    """

    def __init__(self, mem, syms=None, parent=None):
        e_memcanvas.MemoryCanvas.__init__(self, mem, syms=syms)
        QtWidgets.QPlainTextEdit.__init__(self, parent=parent)

        self.setReadOnly(True)
        self._highlighter = VivCanvasColors()

        self._canv_cache = None
        self._canv_curva = None
        self._canv_rend_middle = False

        # Allow our parent to handle these...
        self.setAcceptDrops(False)

    def wheelEvent(self, event):
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
            self.setCenterOnScroll(True)
            self.ensureCursorVisible()

            vmap = self.mem.getMemoryMap(va)
            if vmap is None:
                raise Exception('Invalid Address:%s' % hex(va))

            origva = va
            va, szdiff = self._loc_helper(max(va - size, vmap[0]))
            size += size + szdiff

        ret = super(VQMemoryCanvas, self).renderMemory(va, size, rend=rend)

        if self._canv_rend_middle:
            self._scrollToVa(origva)

        return ret

    @idlethread
    def _scrollToVa(self, va):
        # Let all render events go first
        eatevents()
        # self.centerCursor()
        # self.moveCursor(QtGui.QTextCursor.Start)
        self._selectVa(va)

    @idlethread
    def _selectVa(self, va):
        return

    def _beginRenderMemory(self, va, size, rend):
        self._canv_cache = ''

    def _endRenderMemory(self, va, size, rend):
        # self._appendInside(self._canv_cache)
        self._canv_cache = None

    #####################################################
    def _beginRenderVa(self, va):
        pass

    def _endRenderVa(self, va):
        pass

    #####################################################
    def _beginUpdateVas(self, valist):
        self._canv_cache = ''

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

    # NOTE: doing append / scroll separately allows render to catch up
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

    def _add_raw(self, text):
        # If we are in a call to renderMemory, cache til the end.
        # if self._canv_cache is not None:
        #     self._canv_cache += text
        #     return

        self._appendInside(text)

    def addText(self, text, tag=None):
        if isinstance(text, int):
            text = '%x' % text

        h = self._highlighter.getFormat(tag)
        self._appendInside(text, h)
        # self._add_raw(text)

    @idlethreadsync
    def clearCanvas(self):
        self.clear()

    def contextMenuEvent(self, event):
        va = self._canv_curva
        menu = QtWidgets.QMenu()
        if self._canv_curva:
            self.initMemWindowMenu(va, menu)

        viewmenu = menu.addMenu('view   ')
        viewmenu.addAction("Save frame to HTML", ACT(self._menuSaveToHtml))
        menu.exec_(event.globalPos())

    def initMemWindowMenu(self, va, menu):
        initMemSendtoMenu('0x%.8x' % va, menu)

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
