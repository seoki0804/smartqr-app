import os, PyQt6
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(
    os.path.dirname(PyQt6.__file__),
    "Qt6", "plugins", "platforms"
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QFormLayout,
    QLineEdit, QSpinBox, QPushButton
)
from utils.db.models import init_db, get_connection
from datetime import datetime

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartQR 물품 등록")
        self.resize(400, 200)

        container = QWidget()
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.code_input = QLineEdit()
        self.qty_input  = QSpinBox()
        self.qty_input.setRange(0, 100000)

        generate_btn = QPushButton("QR 생성")
        generate_btn.clicked.connect(self.generate_qr)

        form.addRow("물품명:", self.name_input)
        form.addRow("고유코드:", self.code_input)
        form.addRow("초기 수량:", self.qty_input)
        form.addRow(generate_btn)

        container.setLayout(form)
        self.setCentralWidget(container)

    def generate_qr(self):
        from PyQt6.QtWidgets import QMessageBox
        import qrcode
        import os
        import json

        name = self.name_input.text().strip()
        code = self.code_input.text().strip()
        qty  = self.qty_input.value()

        if not name or not code:
            QMessageBox.warning(self, "입력 오류", "물품명과 고유코드를 모두 입력하세요.")
            return

        # QR 데이터 준비
        data = {"item_name": name, "item_code": code, "initial_qty": qty}
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # 저장할 디렉토리 및 파일 경로 설정
        save_dir = os.path.join(os.getcwd(), "qrcodes")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{code}.png"
        filepath = os.path.join(save_dir, filename)

        # 이미지 파일 저장
        img.save(filepath)

        # Save item to database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO inventory (item_name, item_code, total_stock, created_at) VALUES (?, ?, ?, ?)",
            (name, code, qty, datetime.now().isoformat())
        )
        # If item already exists, update its stock
        cursor.execute(
            "UPDATE inventory SET total_stock = ? WHERE item_code = ?",
            (qty, code)
        )
        conn.commit()
        conn.close()

        # 저장 완료 메시지
        QMessageBox.information(self, "완료", f"QR 코드가 저장되었습니다:\n{filepath}")



if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    # Initialize database
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
