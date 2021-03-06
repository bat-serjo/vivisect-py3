# Some common GUI helpers
from PyQt5 import QtWidgets, QtCore


class RecentlyUsedMixin:
    def __init__(self,
                 menu_name='File',
                 entry_name="Recent",
                 *args, **kwargs):
        self._name = entry_name
        self._menu_name = menu_name
        self._lru = list()
        self._lru_len = 32
        self._dyn_callback = ()

        super(RecentlyUsedMixin, self).__init__(*args, **kwargs)

        self._qs = QtCore.QSettings('vivrecent', parent=self)
        self.load()

    def store(self):
        self._lru = self._lru[:self._lru_len]
        self._qs.setValue(self._name, self._lru)

    def load(self):
        self._lru.clear()
        self._lru.extend(self._qs.value(self._name))
        for i in self._lru.copy():
            if i is None:
                self._lru.remove(i)
        self._lru = self._lru[:self._lru_len]

    def add_item(self, value):
        if value is not None:
            self._lru.insert(0, value)
            self.restore_recent()
            self.store()

    def _recent_pressed(self, value):
        self._lru.remove(value)
        self._lru.insert(0, value)
        self.store()
        self._vq_cli.onecmd('exec "%s"' % value)

    def _populate_recent_menu(self, name=None):
        if name:
            self._recent_pressed(name)
        else:
            return self._lru

    # relies on class having vqAddMenuField
    def restore_recent(self):
        self.vqAddDynMenu(
            '&%s.&%s' % (self._menu_name, self._name),
            self._populate_recent_menu)

        # for i in self._lru:
        #     self.vqAddDynMenu(
        #         '&%s.&%s' % (self._menu_name, self._name),
        #         self._populate_recent_menu)


class ACT:
    def __init__(self, meth, *args, **kwargs):
        self.meth = meth
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.meth(*self.args, **self.kwargs)


class VqtModel(QtCore.QAbstractItemModel):
    columns = ('one', 'two')
    editable = None
    dragable = False

    def __init__(self, rows=()):
        QtCore.QAbstractItemModel.__init__(self)
        # Make sure the rows are lists ( so we can mod them )
        self.rows = [list(row) for row in rows]
        if self.editable is None:
            self.editable = [False, ] * len(self.columns)

    def index(self, row, column, parent):
        return self.createIndex(row, column, self.rows[row])

    def parent(self, index):
        return QtCore.QModelIndex()

    def rowCount(self, index):
        if index.internalPointer() in self.rows:
            return 0
        return len(self.rows)

    def data(self, index, role):
        if role == 0:
            row = index.row()
            col = index.column()
            return self.rows[row][col]

        else:
            return None

    def columnCount(self, index):
        return len(self.columns)

    def headerData(self, column, orientation, role):

        if (orientation == QtCore.Qt.Horizontal and
                    role == QtCore.Qt.DisplayRole):
            return self.columns[column]

        return None

    def flags(self, index):
        if not index.isValid():
            return 0
        flags = QtCore.QAbstractItemModel.flags(self, index)
        col = index.column()
        if self.editable[col]:
            flags |= QtCore.Qt.ItemIsEditable

        if self.dragable:
            flags |= QtCore.Qt.ItemIsDragEnabled  # | QtCore.Qt.ItemIsDropEnabled

        return flags

        # def data(self, index, role):
        # if not index.isValid():
        # return None
        # item = index.internalPointer()
        # if role == QtCore.Qt.DisplayRole:
        # return item.data(index.column())
        # if role == QtCore.Qt.UserRole:
        # return item
        # return None

        # def _vqt_set_data(self, row, col, value):
        # return False

    # def appends(self, rows):

    def append(self, row, parent=QtCore.QModelIndex()):
        # pidx = self.createIndex(parent.row(), 0, parent)
        i = len(self.rows)
        self.beginInsertRows(parent, i, i)
        self.rows.append(row)
        # node = parent.append(rowdata)
        self.endInsertRows()
        self.layoutChanged.emit()

    def setData(self, index, value, role=QtCore.Qt.EditRole):

        if not index.isValid():
            return False

        # If this is the edit role, fire the vqEdited thing
        if role == QtCore.Qt.EditRole:
            print('EDIT ROLE')

            # value = self.vqEdited(node, index.column(), value)
            # if value == None:
            # return False

            row = index.row()
            col = index.column()
            if not self._vqt_set_data(row, col, value):
                return False

        return True

    def pop(self, row, parent=QtCore.QModelIndex()):
        self.beginRemoveRows(parent, row, row + 1)
        self.rows.pop(row)
        self.endRemoveRows()

        # def mimeTypes(self):
        # types = QtCore.QStringList()
        # types.append('vqt/row')
        # return types

        # def mimeData(self, idx):
        # nodes = [ self.rows[i.row()][-1] for i in idx ]
        # mdata = QtCore.QMimeData()
        # mdata.setData('vqt/rows',json.dumps(nodes))
        # return mdata


class VqtView(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super(VqtView, self).__init__(parent=parent)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)

    def getSelectedRows(self):
        ret = []
        rdone = {}
        model = self.model()
        for idx in self.selectedIndexes():

            if rdone.get(idx.row()):
                continue

            rdone[idx.row()] = True
            ret.append(model.mapToSource(idx).internalPointer())

        return ret

    def setModel(self, model):
        smodel = QtCore.QSortFilterProxyModel(parent=self)
        smodel.setSourceModel(model)
        ret = super(VqtView, self).setModel(smodel)
        c = len(model.columns)
        for i in range(c):
            self.resizeColumnToContents(i)
        return ret

    def getModelRows(self):
        return self.model().sourceModel().rows

    def getModelRow(self, idx):
        idx = self.model().mapToSource(idx)
        return idx.row(), idx.internalPointer()


# some no-brainer basics :)

class BasicTreeView(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super(BasicTreeView, self).__init__(parent=parent)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)

    def setModel(self, model):
        ret = super(BasicTreeView, self).setModel(model)
        c = len(model.columns)
        for i in range(c):
            self.resizeColumnToContents(i)
        return ret


class BasicModel(QtCore.QAbstractItemModel):
    columns = ('one', 'two')

    def __init__(self, rows=()):
        super(BasicModel, self).__init__()
        self.rows = list(rows)

    def index(self, row, column, parent):
        return self.createIndex(row, column, self.rows[row])

    def parent(self, index):
        return QtCore.QModelIndex()

    def rowCount(self, index):
        if index.internalPointer() in self.rows:
            return 0
        return len(self.rows)

    def data(self, index, role):
        if role == 0:
            row = index.row()
            col = index.column()
            return self.rows[row][col]

        else:
            return None

    def sort(self, col, order=QtCore.Qt.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        self.rows.sort(cmp=lambda x, y: cmp(x[col], y[col]))
        if order == QtCore.Qt.DescendingOrder:
            self.rows.reverse()
        self.layoutChanged.emit()

    def columnCount(self, index):
        return len(self.columns)

    def headerData(self, column, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.columns[column]

        return None


class VBox(QtWidgets.QVBoxLayout):
    def __init__(self, *widgets):
        super(VBox, self).__init__()
        self.setContentsMargins(2, 2, 2, 2)
        self.setSpacing(4)
        for w in widgets:
            if w is None:
                self.addStretch()
                continue
            self.addWidget(w)


class HBox(QtWidgets.QHBoxLayout):
    def __init__(self, *widgets):
        super(HBox, self).__init__()
        self.setContentsMargins(2, 2, 2, 2)
        self.setSpacing(4)
        for w in widgets:
            if w is None:
                self.addStretch()
                continue
            self.addWidget(w)