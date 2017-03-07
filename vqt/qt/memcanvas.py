from vqt.main import *
from vqt.common import *

import envi.memcanvas as e_memcanvas


class VQMemoryCanvas(e_memcanvas.MemoryCanvas, QtWidgets.QWidget):
    def __init__(self, mem, syms=None, parent=None):
        e_memcanvas.MemoryCanvas.__init__(self, mem, syms=syms)
        QtWidgets.QWidget.__init__(self, parent=parent)

        self._editor = QtWidgets.QTextEdit(self)
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self._editor)
        self.setLayout(vbox)

        self._canv_cache = None
        self._canv_curva = None
        self._canv_rend_middle = False

        # Allow our parent to handle these...
        self.setAcceptDrops(False)

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
            self._scrollToVa(origva)

        return ret

    @idlethread
    def _scrollToVa(self, va):
        eatevents()  # Let all render events go first
        self._selectVa(va)

    @idlethread
    def _selectVa(self, va):
        return

    def _beginRenderMemory(self, va, size, rend):
        self._canv_cache = ''

    def _endRenderMemory(self, va, size, rend):
        self._appendInside(self._canv_cache)
        self._canv_cache = None

    def _beginRenderVa(self, va):
        # self._add_raw('\n')
        pass

    def _endRenderVa(self, va):
        # self._add_raw('\n')
        pass

    def _beginUpdateVas(self, valist):
        self._canv_cache = ''

    def _endUpdateVas(self):
        self._canv_cache = None

    def _beginRenderPrepend(self):
        self._canv_cache = ''
        self._canv_ppjump = self._canv_rendvas[0][0]

    def _endRenderPrepend(self):
        self._canv_cache = None
        self._scrollToVa(self._canv_ppjump)

    def _beginRenderAppend(self):
        self._canv_cache = ''

    def _endRenderAppend(self):
        self._canv_cache = None

    def getNameTag(self, name, typename='name'):
        """
        Return a "tag" for this memory canvas.  In the case of the
        vdb tags, they are a tuple of html text (<opentag>, <closetag>)
        """
        return "", ""

    def getVaTag(self, va):
        # The "class" will be the same that we get back from goto event
        return "", ""

    # NOTE: doing append / scroll separately allows render to catch up
    @idlethread
    def _appendInside(self, text):
        self._editor.insertPlainText(text)

    def _add_raw(self, text):
        # If we are in a call to renderMemory, cache til the end.
        if self._canv_cache is not None:
            self._canv_cache += text
            return

        self._appendInside(text)

    def addText(self, text, tag=None):
        if isinstance(text, int):
            text = '%x' % text

        if tag is not None:
            otag, ctag = tag
            text = otag + text + ctag

        self._add_raw(text)

    @idlethreadsync
    def clearCanvas(self):
        self._editor.clear()

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
        # if fname is not None:
            # _html = self.page().mainFrame().toHtml()
            # open(fname, 'w').write(_html)


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
