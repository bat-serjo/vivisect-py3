import math
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


class VivGraphicsScene(e_qt_memory.EnviNavMixin, QtWidgets.QGraphicsScene):
    def __init__(self, *args, **kwargs):
        QtWidgets.QGraphicsScene.__init__(self, *args, **kwargs)
        try:
            e_qt_memory.EnviNavMixin.__init__(self)
        except:
            pass

    def dragMoveEvent(self, event: QtWidgets.QGraphicsSceneDragDropEvent):
        event.accept()

    def enviNavGoto(self, expr, sizeexpr=None, rend=None):
        self.parent().enviNavGoto(expr, sizeexpr, rend)


def wrapPathItem(pitem: QtWidgets.QGraphicsPathItem):
    def hoverEnterEvent(self: QtWidgets.QGraphicsPathItem, event: QtWidgets.QGraphicsSceneHoverEvent):
        self._old_brush = self.brush()
        self.setBrush(QtGui.QBrush(QtGui.QColor('#00aaff')))
        event.accept()

    def hoverLeaveEvent(self: QtWidgets.QGraphicsPathItem, event: QtWidgets.QGraphicsSceneHoverEvent):
        self.setBrush(self._old_brush)
        event.accept()

    pitem.setAcceptHoverEvents(True)
    pitem.hoverEnterEvent = hoverEnterEvent
    pitem.hoverLeaveEvent = hoverLeaveEvent


# vq_memory.VivCanvasBase
class VQVivFuncGraphCanvas(e_qt_memory.EnviNavMixin, QtWidgets.QGraphicsView):
    paintUp = pyqtSignal()
    paintDown = pyqtSignal()
    paintMerge = pyqtSignal()
    refreshSignal = pyqtSignal()

    bg_color = '#212121'
    true_edge_color = '#4CAF50'
    false_edge_color = "#F44336"
    edge_width = 3

    zoom_in = 1.25
    move_modifier = QtCore.Qt.ShiftModifier

    def __init__(self, vw, syms, parent, *args, **kwargs):
        self.vw = vw
        self.syms = syms

        QtWidgets.QGraphicsView.__init__(self, parent=parent)
        e_qt_memory.EnviNavMixin.__init__(self)

        self.scene = VivGraphicsScene(parent=self)
        self.setScene(self.scene)

        self.scene.setStickyFocus(True)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(self.bg_color)))
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHints(self.renderHints() | QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)

        self._orig_transform = self.transform()
        self._edge_pen = QtGui.QPen(QtGui.QBrush(QtGui.QColor(self.true_edge_color)), self.edge_width,
                                    QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)

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
            if delta.y() > 0:
                scale = self.zoom_in
            else:
                scale = 1 / self.zoom_in

            # Set Anchors
            self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
            self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)

            cur_pos = self.mapToScene(event.pos())
            self.scale(scale, scale)
            new_pos = self.mapToScene(event.pos())
            delta_zoomed = new_pos - cur_pos
            self.translate(delta_zoomed.x(), delta_zoomed.y())

            event.accept()
            return

        return super(VQVivFuncGraphCanvas, self).wheelEvent(event)

    def clear(self):
        self.scene.clear()
        self.items().clear()
        self.viewport().update()
        self.setTransform(self._orig_transform)
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
            o = vq_memory.VivCanvasBase(self.vw, self.syms, parent=None)
            o.addRenderer('Viv', self._rend)
            o.setRenderer('Viv')
            o.setFixedLocation(True)

            # tell it what to render
            o.renderMemory(cbva, cbsize)
            proxy = None

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

        # only after the rendition is done we can do this
        for nid, nprops in self.func_graph.getNodes():
            cbva = nprops.get('cbva')
            o, proxy = self._block_views[cbva]

            w, h = o.getBestDimensions()
            o.resize(w, h)

            # store the dimensions of the canvas
            self.func_graph.setNodeProp((nid, nprops), 'size', (w, h))

        # calculate the layout positions based on the canvas sizes
        # we have created the canvases and have their dimensions, lay them out
        self.graph_layout = vg_dynadag.DynadagLayout(self.func_graph)
        self.graph_layout._barry_count = 20
        self.graph_layout.layoutGraph()

        # width, height = self.graph_layout.getLayoutSize()
        for nid, nprops in self.func_graph.getNodes():
            cbva = nprops.get('cbva')
            if cbva is None:
                continue

            xpos, ypos = nprops.get('position')
            o, proxy = self._block_views[cbva]

            # since we will be adding the canvases to a graphics scene
            # we have to wrap then into a proxy
            proxy = QtWidgets.QGraphicsProxyWidget(None, QtCore.Qt.Window)
            proxy.setWidget(o)
            proxy.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)
            proxy.resize(o.width(), o.height())
            proxy.setPos(float(xpos), float(ypos))

            self.scene.addItem(proxy)
            self._block_views[cbva] = o, proxy

        self.scene.setSceneRect(self.scene.itemsBoundingRect())

        ############################################################
        # Draw in some EDGE lines!
        for eid, n1, n2, einfo in self.func_graph.getEdges():
            points = einfo.get('edge_points')

            ppath = QtGui.QPainterPath()
            ppath.moveTo(*points[0])
            [ppath.lineTo(x, y) for (x, y) in points[1:]]
            pitem = self.scene.addPath(ppath, self._edge_pen)
            wrapPathItem(pitem)
            # pitem.setFlags(QtWidgets.QGraphicsItem.Hov)

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

    def enviNavGoto(self, expr, sizeexpr=None, rend=None):
        return self.parent().enviNavGoto(expr, sizeexpr, rend)

    def refresh(self):
        """
        Redraw the function graph (actually, tells the View to do it)
        """
        self.refreshSignal.emit()

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
        pass

    def _hotkey_inczoom(self):
        pass

    def _hotkey_deczoom(self):
        pass

    def refresh(self):
        """
        Cause the Function Graph to redraw itself.
        This is particularly helpful because comments and name changes don't
        immediately display.  Perhaps someday this will update only the blocks
        that have changed since last update, and be fast, so we can update
        after every change.
        """
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

    def enviNavGoto(self, expr, sizeexpr=None, rend=None):
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
            self.updateWindowTitle()
            return

        if fva is None:
            self.mem_canvas.addText('0x%.8x is not in a function!' % addr)
            return

        self.mem_canvas.renderFunctionGraph(fva)
        self.updateWindowTitle()

        self._renderDoneSignal.emit()

    def loadDefaultRenderers(self):
        vivrend = viv_rend.WorkspaceRenderer(self.vw)
        self.mem_canvas.addRenderer('Viv', vivrend)
        self.mem_canvas.setRenderer('Viv')

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
