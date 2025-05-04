# File: smartqr-app/main.py

import os, PyQt6
# macOS용 Qt 플랫폼 플러그인 경로 지정 (없으면 cocoa 오류)
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(
    os.path.dirname(PyQt6.__file__),
    "Qt6", "plugins", "platforms"
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QMessageBox, QInputDialog
)
import sys

# 스캔 모듈 임포트
from utils.qr_tools import scan_qr_from_camera


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartQR 물품 등록 및 재고관리")
        self.resize(400, 300)

        container = QWidget()
        form = QFormLayout()

        # ————— 물품 등록 필드 —————
        self.name_input = QLineEdit()   # 물품명 입력
        self.code_input = QLineEdit()   # 고유코드 입력
        self.qty_input  = QSpinBox()    # 초기 수량 입력
        self.qty_input.setRange(0, 100000)

        generate_btn = QPushButton("QR 생성")
        generate_btn.clicked.connect(self.generate_qr)

        form.addRow("물품명:", self.name_input)
        form.addRow("고유코드:", self.code_input)
        form.addRow("초기 수량:", self.qty_input)
        form.addRow(generate_btn)

        # ————— 재고 입/출고 스캔 버튼 —————
        scan_btn = QPushButton("QR 스캔 (재고 입/출고)")
        scan_btn.clicked.connect(self.handle_scan)
        form.addRow(scan_btn)

        container.setLayout(form)
        self.setCentralWidget(container)


    def generate_qr(self):
        """QR 생성 기능 (1단계)"""
        import qrcode, json

        name = self.name_input.text().strip()
        code = self.code_input.text().strip()
        qty  = self.qty_input.value()

        if not name or not code:
            QMessageBox.warning(self, "입력 오류", "물품명과 고유코드를 모두 입력하세요.")
            return

        data = {"item_name": name, "item_code": code, "initial_qty": qty}
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        save_dir = os.path.join(os.getcwd(), "qrcodes")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{code}.png")
        img.save(filepath)

        QMessageBox.information(self, "완료", f"QR 코드가 저장되었습니다:\n{filepath}")


    def handle_scan(self):
        """QR 스캔 후 재고 입/출고 처리 (2단계)"""
        data = scan_qr_from_camera()
        if not data:
            QMessageBox.information(self, "알림", "QR 코드 인식에 실패했습니다.")
            return

        # QR에서 읽은 물품 이름/코드 꺼내기
        item_name = data.get("item_name", "")
        item_code = data.get("item_code", "")

        # 사용자에게 입/출고 수량 입력받기
        qty, ok = QInputDialog.getInt(
            self,
            "수량 입력",
            f"{item_name} 수량 (+입고, -출고):",
        )
        if not ok:
            return

        # TODO: 실제 DB에서 가져온 재고(total_stock)에 qty를 더하거나 빼서 업데이트
        # e.g., total_stock = fetch_from_db(item_code) + qty
        #       update_db(item_code, total_stock)

        QMessageBox.information(
            self,
            "완료",
            f"{item_name} 재고가 {qty} 만큼 변경되었습니다."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())