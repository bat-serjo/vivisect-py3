import sys

from PyQt5.Qsci import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


class MyLexer(QsciLexerCustom):

    def __init__(self, parent):
        super(MyLexer, self).__init__(parent)

        # Default text settings
        # ----------------------
        self.setDefaultColor(QColor("#ff000000"))
        self.setDefaultPaper(QColor("#ffffffff"))
        self.setDefaultFont(QFont("Consolas", 14))

        # Initialize colors per style
        # ----------------------------
        self.setColor(QColor("#ff000000"), 0)  # Style 0: black
        self.setColor(QColor("#ff7f0000"), 1)  # Style 1: red
        self.setColor(QColor("#ff0000bf"), 2)  # Style 2: blue
        self.setColor(QColor("#ff007f00"), 3)  # Style 3: green

        # Initialize paper colors per style
        # ----------------------------------
        self.setPaper(QColor("#ffffffff"), 0)  # Style 0: white
        self.setPaper(QColor("#ffffffff"), 1)  # Style 1: white
        self.setPaper(QColor("#ffffffff"), 2)  # Style 2: white
        self.setPaper(QColor("#ffffffff"), 3)  # Style 3: white

        # Initialize fonts per style
        # ---------------------------
        self.setFont(QFont("Consolas", 14, weight=QFont.Bold), 0)  # Style 0: Consolas 14pt
        self.setFont(QFont("Consolas", 14, weight=QFont.Bold), 1)  # Style 1: Consolas 14pt
        self.setFont(QFont("Consolas", 14, weight=QFont.Bold), 2)  # Style 2: Consolas 14pt
        self.setFont(QFont("Consolas", 14, weight=QFont.Bold), 3)  # Style 3: Consolas 14pt

        # Define style 1 to be hotspot
        # -----------------------------
        editor = self.parent()
        editor.SendScintilla(editor.SCI_STYLESETHOTSPOT, 1, True)

    def language(self):
        print('language')

    def description(self, style_nr):
        print(style_nr)

    def styleText(self, start, end):
        # Called every time the editors text has changed
        print(start, end)


class CustomMainWindow(QMainWindow):
    def __init__(self):
        super(CustomMainWindow, self).__init__()

        self.setGeometry(300, 300, 800, 400)
        self.setWindowTitle("QScintilla Test")

        # 3. Place a button
        self.__btn = QPushButton("Qsci")
        self.__btn.clicked.connect(self.__btn_action)

        self.__editor = QsciScintilla()
        self.__editor.setText("Hello\n")
        self.__editor.append("world")
        # self.__editor.setLexer(MyLexer(self.__editor))
        self.__editor.setUtf8(True)  # Set encoding to UTF-8

        self.__frm = QFrame()
        self.setCentralWidget(self.__frm)
        self.vbox = QVBoxLayout(self.__frm)
        self.vbox.addWidget(self.__btn)
        self.vbox.addWidget(self.__editor)

        self.show()

    def __btn_action(self):
        print("Hello World!")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # QApplication.setStyle(QStyleFactory.create('Fusion'))
    myGUI = CustomMainWindow()

    sys.exit(app.exec_())
