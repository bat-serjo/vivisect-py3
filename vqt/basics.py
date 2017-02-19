"""
A place for some no-brainer basics :)
"""

from PyQt5 import QtCore, QtWidgets


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

        if (orientation == QtCore.Qt.Horizontal and
                    role == QtCore.Qt.DisplayRole):
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


class ACT:
    def __init__(self, meth, *args, **kwargs):
        self.meth = meth
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.meth(*self.args, **self.kwargs)
