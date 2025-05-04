import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartQR 앱 시작")
        self.setGeometry(100, 100, 600, 400)

        label = QLabel("SmartQR 앱이 실행되었습니다.", self)
        label.move(50, 50)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())