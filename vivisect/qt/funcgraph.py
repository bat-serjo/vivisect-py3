import time
import itertools
import collections

from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal, QPoint

import vqt.saveable as vq_save
import vqt.hotkeys as vq_hotkey
import vivisect.base as viv_base
import vqt.qt.memory as e_qt_memory
import vivisect.renderers as viv_rend
import vivisect.qt.memory as vq_memory
import vqt.qt.memcanvas as e_qt_memcanvas
import vivisect.qt.ctxmenu as vq_ctxmenu

import visgraph.layouts.dynadag as vg_dynadag
import vivisect.tools.graphutil as viv_graphutil

from vqt.common import *
from vqt.main import idlethread, eatevents, workthread, vqtevent


# vq_memory.VivCanvasBase
class VQVivFuncGraphCanvas(QtWidgets.QGraphicsView):
    paintUp = pyqtSignal()
    paintDown = pyqtSignal()
    paintMerge = pyqtSignal()
    refreshSignal = pyqtSignal()

    bg_color = '#303030'

    def __init__(self, vw, syms, parent, *args, **kwargs):
        self.vw = vw
        self.syms = syms

        super(VQVivFuncGraphCanvas, self).__init__(parent=parent)
        # vq_memory.VivCanvasBase.__init__(self, *args, **kwargs)

        self.scene = QtWidgets.QGraphicsScene(parent=self)
        self.setScene(self.scene)

        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(self.bg_color)))

        ##################################################################
        self.curs = QtGui.QCursor()

        self.lastpos = None
        self.basepos = None

        ##################################################################
        # Function graph related stuff

        # holds the memory canvas instances for each basic block
        self._block_views = dict()
        self.func_va = None
        self.func_graph = None
        # the layout used for this graph
        self.graph_layout = None

        self._rend = viv_rend.WorkspaceRenderer(vw)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            delta = event.angleDelta()
            factord = delta / 1000.0
            self.setZoomFactor(self.zoomFactor() + factord)
            event.accept()
            return

        return super(VQVivFuncGraphCanvas, self).wheelEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            x = event.globalX()
            y = event.globalY()
            if self.lastpos:
                dx = -(x - self.lastpos[0])
                dy = -(y - self.lastpos[1])
                # dx = x - self.lastpos[0]
                # dy = y - self.lastpos[1]
                # self.page().mainFrame().scroll(dx, dy)

                self.curs.setPos(*self.basepos)
            else:
                self.lastpos = (x, y)
                self.basepos = (x, y)

            event.accept()
            return

        self.lastpos = None
        return super(VQVivFuncGraphCanvas, self).mouseMoveEvent(event)

    def clear(self):
        self.scene.clear()
        self.items().clear()
        self.viewport().update()
        self.updateScene([self.scene.sceneRect()])

        self._block_views.clear()
        self.func_graph = None

    def renderFunctionGraph(self, fva, graph=None):
        self.clear()

        self.func_va = fva
        # self.graph = self.vw.getFunctionGraph(fva)

        if graph is None:
            graph = viv_graphutil.buildFunctionGraph(self.vw, fva, revloop=True)

        self.func_graph = graph

        # For each node create a memory canvas and render it there
        for nid, nprops in self.func_graph.getNodes():
            # cbva, cbsize = self.graph.getCodeBlockBounds(node)
            cbva = nprops.get('cbva')
            cbsize = nprops.get('cbsize')

            # create the canvas
            o = vq_memory.VivCanvasBase(self.vw, self.syms, parent=self)
            o.addRenderer('Viv', self._rend)
            o.setRenderer('Viv')
            o.setFixedLocation(True)

            # tell it what to render
            o.renderMemory(cbva, cbsize)

            # since we will be adding the canvases to a graphics scene
            # we have to wrap then into a proxy
            proxy = QtWidgets.QGraphicsProxyWidget()
            proxy.setWidget(o)

            # now store the data in the dict
            self._block_views[cbva] = o, proxy

        # Let the renders complete...
        eatevents()
        done = False
        while done is False:
            done = True
            for cbva, (o, proxy) in self._block_views.items():
                if o.isFixedLocationRenderingComplete() is False:
                    done = False
                    time.sleep(0.1)
                    # eatevents()

        # only after the rendition is done we can do this
        for nid, nprops in self.func_graph.getNodes():
            cbva = nprops.get('cbva')
            o, proxy = self._block_views[cbva]
            self.scene.addItem(proxy)
            o.show()

            sz = o.document().size()
            # o.resize(sz.width()+5, sz.height()+5)
            o.adjustSize()
            # store the dimensions of the canvas
            self.func_graph.setNodeProp((nid, nprops), 'size', (o.width(), o.height()))

        # we have created the canvases and have their dimensions, lay them out
        self.graph_layout = vg_dynadag.DynadagLayout(self.func_graph)
        self.graph_layout._barry_count = 20
        self.graph_layout.layoutGraph()

        width, height = self.graph_layout.getLayoutSize()
        for nid, nprops in self.func_graph.getNodes():
            cbva = nprops.get('cbva')
            if cbva is None:
                continue

            xpos, ypos = nprops.get('position')
            o, proxy = self._block_views[cbva]
            o.move(float(xpos), float(ypos))

        self.show()

        # Draw in some edge lines!
        for eid, n1, n2, einfo in self.func_graph.getEdges():
            points = einfo.get('edge_points')
            pointstr = ' '.join(['%d,%d' % (x, y) for (x, y) in points])

            # frame.evaluateJavaScript('drawSvgLine("%s", "edge_%.8s", "%s");' % (svgid, eid, pointstr))

            # self.updateWindowTitle()

            # FIXME
            # def closeEvent(self, event):
            # FIXME this doesn't actually do anything...
            # self.parentWidget().delEventCore(self)
            # return e_mem_qt.VQMemoryWindow.closeEvent(self, event)


    # def renderMemory(self, va, size, rend=None):
    #     # For the funcgraph canvas, this will be called once per code block
    #     # --CLEAR--
    #     return
    #
    #     # # Check if we have a codeblock element already...
    #     # frame = self.page().mainFrame()
    #     # canvelem = frame.findFirstElement('#memcanvas')
    #     #
    #     # elem = frame.findFirstElement('#codeblock_%.8x' % va)
    #     # if elem.isNull():
    #     #     # Lets add a codeblock element for this
    #     #     canvelem.appendInside('<div class="codeblock" id="codeblock_%.8x"></div>' % va)
    #     #
    #     # self._canv_rendtagid = '#codeblock_%.8x' % va
    #     #
    #     # ret = super(VQVivFuncGraphCanvas, self).renderMemory(va, size, rend=rend)
    #     # # ret = self.renderMemory(va, size, rend=rend)
    #     #
    #     # self._canv_rendtagid = '#memcanvas'
    #     #
    #     # return ret

    def contextMenuEvent(self, event):
        if self._canv_curva:
            menu = vq_ctxmenu.buildContextMenu(self.vw, va=self._canv_curva, parent=self)
        else:
            menu = QtWidgets.QMenu(parent=self)

        self.viewmenu = menu.addMenu('view   ')
        self.viewmenu.addAction("Save frame to HTML", ACT(self._menuSaveToHtml))
        self.viewmenu.addAction("Refresh", ACT(self.refresh))
        self.viewmenu.addAction("Paint Up", ACT(self.paintUp.emit))
        self.viewmenu.addAction("Paint Down", ACT(self.paintDown.emit))
        self.viewmenu.addAction("Paint Down until remerge", ACT(self.paintMerge.emit))

        viewmenu = menu.addMenu('view   ')
        viewmenu.addAction("Save frame to HTML", ACT(self._menuSaveToHtml))
        viewmenu.addAction("Refresh", ACT(self.refresh))

        menu.exec_(event.globalPos())

    def _navExpression(self, expr):
        if self._canv_navcallback:
            self._canv_navcallback(expr)

    def refresh(self):
        """
        Redraw the function graph (actually, tells the View to do it)
        """
        self.refreshSignal.emit()

    @idlethread
    def setScrollPosition(self, x, y):
        """
        Sets the view reticle to an absolute scroll position
        """
        point = QPoint(x, y)
        # self.page().mainFrame().setScrollPosition(point)

    def applyColorMap(self, cmap: dict):
        pass

    def addText(self, text, tag=None):
        self.clear()
        self.scene.addText(text)


class VQVivFuncgraphView(vq_hotkey.HotKeyMixin, e_qt_memory.EnviNavMixin,
                         QtWidgets.QWidget, vq_save.SaveableWidget,
                         viv_base.VivEventCore):

    _renderDoneSignal = pyqtSignal()
    viewidx = itertools.count()
    bg_color = '#303030'

    def __init__(self, vw, vwqgui):
        self.vw = vw
        self.fva = None
        self.graph = None
        self.vwqgui = vwqgui
        self.history = collections.deque((), 100)

        QtWidgets.QWidget.__init__(self, parent=vwqgui)
        vq_hotkey.HotKeyMixin.__init__(self)
        viv_base.VivEventCore.__init__(self, vw)
        e_qt_memory.EnviNavMixin.__init__(self)

        self.mem_canvas = VQVivFuncGraphCanvas(vw, syms=vw, parent=self)
        # self.mem_canvas.setNavCallback(self.enviNavGoto)
        # self.mem_canvas.refreshSignal.connect(self.refresh)
        # self.mem_canvas.paintUp.connect(self._hotkey_paintUp)
        # self.mem_canvas.paintDown.connect(self._hotkey_paintDown)
        # self.mem_canvas.paintMerge.connect(self._hotkey_paintMerge)

        # self.loadDefaultRenderers()

        # create the top row of widgets. History and address entry
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(2, 2, 2, 2)
        hbox.setSpacing(4)

        self.histmenu = QtWidgets.QMenu(parent=self)
        self.histmenu.aboutToShow.connect(self._histSetupMenu)

        self.hist_button = QtWidgets.QPushButton('History', parent=self)
        self.hist_button.setMenu(self.histmenu)

        self.addr_entry = QtWidgets.QLineEdit(parent=self)
        self.addr_entry.returnPressed.connect(self._renderMemory)

        hbox.addWidget(self.hist_button)
        hbox.addWidget(self.addr_entry)

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)
        vbox.addLayout(hbox)
        vbox.addWidget(self.mem_canvas)

        self.setLayout(vbox)

        self.setEnviNavName('FuncGraph%d' % next(self.viewidx))
        self.updateWindowTitle()

        self._renderDoneSignal.connect(self._refresh_cb)

        # Do these last so we are all setup...
        vwqgui.addEventCore(self)
        vwqgui.vivMemColorSignal.connect(self.mem_canvas.applyColorMap)

        self.addHotKey('esc', 'mem:histback')
        self.addHotKeyTarget('mem:histback', self._hotkey_histback)
        self.addHotKey('ctrl+0', 'funcgraph:resetzoom')
        self.addHotKeyTarget('funcgraph:resetzoom', self._hotkey_resetzoom)
        self.addHotKey('ctrl+=', 'funcgraph:inczoom')
        self.addHotKeyTarget('funcgraph:inczoom', self._hotkey_inczoom)
        self.addHotKey('ctrl+-', 'funcgraph:deczoom')
        self.addHotKeyTarget('funcgraph:deczoom', self._hotkey_deczoom)
        self.addHotKey('f5', 'funcgraph:refresh')
        self.addHotKeyTarget('funcgraph:refresh', self.refresh)
        self.addHotKey('ctrl+u', 'funcgraph:paintup')
        self.addHotKeyTarget('funcgraph:paintup', self._hotkey_paintUp)
        self.addHotKey('ctrl+d', 'funcgraph:paintdown')
        self.addHotKeyTarget('funcgraph:paintdown', self._hotkey_paintDown)
        self.addHotKey('ctrl+m', 'funcgraph:paintmerge')
        self.addHotKeyTarget('funcgraph:paintmerge', self._hotkey_paintMerge)

    def _hotkey_histback(self):
        if len(self.history) >= 2:
            self.history.pop()
            expr = self.history.pop()
            self.enviNavGoto(expr)

    def _hotkey_resetzoom(self):
        self.mem_canvas.setZoomFactor(1)

    def _hotkey_inczoom(self):
        newzoom = self.mem_canvas.zoomFactor()
        if 1 > newzoom > .75:
            newzoom = 1
        elif newzoom < .5:
            newzoom += .125
        else:
            newzoom += .25

        if newzoom < 0:
            return

        # self.vw.vprint("NEW ZOOM    %f" % newzoom)
        self.mem_canvas.setZoomFactor(newzoom)

    def _hotkey_deczoom(self):
        newzoom = self.mem_canvas.zoomFactor()
        if newzoom <= .5:
            newzoom -= .125
        else:
            newzoom -= .25

        # self.vw.vprint("NEW ZOOM    %f" % newzoom)
        self.mem_canvas.setZoomFactor(newzoom)

    def refresh(self):
        """
        Cause the Function Graph to redraw itself.
        This is particularly helpful because comments and name changes don't
        immediately display.  Perhaps someday this will update only the blocks
        that have changed since last update, and be fast, so we can update
        after every change.
        """
        self.clearText()
        self.fva = None
        self._renderMemory()

    @workthread
    def _refresh_cb(self):
        """
        This is a hack to make sure that when _renderMemory() completes,
        _refresh_3() gets run after all other rendering events yet to come.
        """
        pass

    def _histSetupMenu(self):
        self.histmenu.clear()

        history = []
        for expr in self.history:
            addr = self.vw.parseExpression(expr)
            menustr = '0x%.8x' % addr
            sym = self.vw.getSymByAddr(addr)
            if sym is not None:
                menustr += ' - %s' % repr(sym)

            history.append((menustr, expr))

        history.reverse()
        for menustr, expr in history:
            self.histmenu.addAction(menustr, ACT(self._histSelected, expr))

    def _histSelected(self, expr):
        while self.history.pop() != expr:
            pass
        self.enviNavGoto(expr)

    def enviNavGoto(self, expr, sizeexpr=None):
        self.addr_entry.setText(expr)
        self.history.append(expr)
        self.updateWindowTitle()
        self._renderMemory()

    def vqGetSaveState(self):
        return {'expr': str(self.addr_entry.text()), }

    def vqSetSaveState(self, state):
        expr = state.get('expr', '')
        self.enviNavGoto(expr)

    def updateWindowTitle(self):
        ename = self.getEnviNavName()
        expr = str(self.addr_entry.text())
        try:
            va = self.vw.parseExpression(expr)
            smartname = self.vw.getName(va, smart=True)
            self.setWindowTitle('%s: %s (0x%x)' % (ename, smartname, va))
        except:
            self.setWindowTitle('%s: %s (0x----)' % (ename, expr))

    def _buttonSaveAs(self):
        pass
        # frame = self.mem_canvas.page().mainFrame()
        # elem = frame.findFirstElement('#mainhtml')
        # h = elem.toOuterXml()
        ## h = frame.toHtml()
        # open('test.html', 'wb').write(str(h))

    @idlethread
    def _renderMemory(self):

        expr = str(self.addr_entry.text())
        if not expr:
            return

        try:
            addr = self.vw.parseExpression(expr)
        except Exception as e:
            self.mem_canvas.addText('Invalid Address: %s (%s)' % (expr, e))
            return

        fva = self.vw.getFunction(addr)
        if fva == self.fva:
            # self.mem_canvas.page().mainFrame().scrollToAnchor('viv:0x%.8x' % addr)
            self.updateWindowTitle()
            return

        if fva is None:
            self.vw.vprint('0x%.8x is not in a function!' % addr)
            return

        self.clearText()
        self.mem_canvas.renderFunctionGraph(fva)
        self.updateWindowTitle()

        self._renderDoneSignal.emit()

    def loadDefaultRenderers(self):
        vivrend = viv_rend.WorkspaceRenderer(self.vw)
        self.mem_canvas.addRenderer('Viv', vivrend)
        self.mem_canvas.setRenderer('Viv')

    def clearText(self):
        # --CLEAR--
        return
        # Pop the svg and reset #memcanvas
        frame = self.mem_canvas.page().mainFrame()
        if self.fva:
            svgid = '#funcgraph_%.8x' % self.fva
            svgelem = frame.findFirstElement(svgid)
            svgelem.removeFromDocument()

        memelem = frame.findFirstElement('#memcanvas')
        memelem.setInnerXml(' ')

    def _hotkey_paintUp(self, va=None):
        """
        Paint the VA's from the selected basic block up to all possible 
        non-looping starting points.
        """
        graph = viv_graphutil.buildFunctionGraph(self.vw, self.fva, revloop=True)
        startva = self.mem_canvas._canv_curva
        if startva is None:
            return

        viv_graphutil.preRouteGraphUp(graph, startva, mark='hit')

        count = 0
        colormap = {}
        for node in graph.getNodesByProp('hit'):
            count += 1
            off = 0
            cbsize = node[1].get('cbsize')
            if cbsize is None:
                raise Exception('node has no cbsize: %s' % repr(node))

            # step through opcode for a node
            while off < cbsize:
                op = self.vw.parseOpcode(node[0] + off)
                colormap[op.va] = 'orange'
                off += len(op)

        self.vw.vprint("Colored Blocks: %d" % count)
        vqtevent('viv:colormap', colormap)
        return colormap

    def _hotkey_paintDown(self, va=None):
        """
        Paint the VA's from the selected basic block down to all possible
        non-looping blocks.  This is valuable for determining what code can
        execute from any starting basic block, without a loop.
        """
        # TODO: make overlapping colors available for multiple paintings

        graph = viv_graphutil.buildFunctionGraph(self.vw, self.fva, revloop=True)
        startva = self.mem_canvas._canv_curva
        if startva is None:
            return

        viv_graphutil.preRouteGraphDown(graph, startva, mark='hit')

        count = 0
        colormap = {}
        for node in graph.getNodesByProp('hit'):
            count += 1
            off = 0
            cbsize = node[1].get('cbsize')
            if cbsize is None:
                raise Exception('node has no cbsize: %s' % repr(node))

            # step through opcode for a node
            while off < cbsize:
                op = self.vw.parseOpcode(node[0] + off)
                colormap[op.va] = 'brown'
                off += len(op)

        self.vw.vprint("Colored Blocks: %d" % count)
        vqtevent('viv:colormap', colormap)
        return colormap

    def _hotkey_paintMerge(self, va=None):
        """
        same as paintdown but only until the graph remerges
        """

        graph = viv_graphutil.buildFunctionGraph(self.vw, self.fva, revloop=True)
        startva = self.mem_canvas._canv_curva
        if startva is None:
            return

        viv_graphutil.findRemergeDown(graph, startva)

        count = 0
        colormap = {}
        for node in graph.getNodesByProp('hit'):
            count += 1
            off = 0
            cbsize = node[1].get('cbsize')
            if cbsize is None:
                raise Exception('node has no cbsize: %s' % repr(node))

            # step through opcode for a node
            while off < cbsize:
                op = self.vw.parseOpcode(node[0] + off)
                colormap[op.va] = 'brown'
                off += len(op)

        self.vw.vprint("Colored Blocks: %d" % count)
        vqtevent('viv:colormap', colormap)
        return colormap


@idlethread
def showFunctionGraph(fva, vw, vwqgui):
    view = VQVivFuncgraphView(fva, vw, vwqgui)
    view.show()
