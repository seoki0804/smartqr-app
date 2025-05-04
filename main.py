# File: smartqr-app/main.py

import os, sys, json
# macOS용 Qt 플랫폼 플러그인 경로 지정 (없으면 cocoa 오류)
import PyQt6
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(
    os.path.dirname(PyQt6.__file__),
    "Qt6", "plugins", "platforms"
)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFormLayout,
    QLineEdit, QSpinBox, QPushButton,
    QMessageBox, QInputDialog,
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem
)
from datetime import datetime

# DB 모듈 임포트
from utils.db.models import init_db, get_connection
# QR 스캔 모듈 임포트
from utils.qr_tools import scan_qr_from_camera

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartQR 물품 등록 및 재고관리")
        self.resize(400, 350)

        # 폼 레이아웃 생성
        container = QWidget()
        form = QFormLayout()

        # ————— 물품 등록 필드 —————
        self.name_input = QLineEdit()    # 물품명 입력
        self.code_input = QLineEdit()    # 고유코드 입력
        self.qty_input  = QSpinBox()     # 초기 수량 입력
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

        # ————— 재고 현황 보기 버튼 —————
        view_btn = QPushButton("재고 현황 보기")
        view_btn.clicked.connect(self.show_inventory)
        form.addRow(view_btn)

        container.setLayout(form)
        self.setCentralWidget(container)

    def generate_qr(self):
        """
        물품 정보 입력 후 QR 코드 생성, 이미지 저장, DB에 물품 등록/업데이트
        """
        import qrcode

        name = self.name_input.text().strip()
        code = self.code_input.text().strip()
        qty  = self.qty_input.value()

        if not name or not code:
            QMessageBox.warning(self, "입력 오류", "물품명과 고유코드를 모두 입력하세요.")
            return

        # QR 데이터 준비 (JSON 문자열)
        data = {"item_name": name, "item_code": code, "initial_qty": qty}
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # QR 이미지 저장 폴더/파일 경로
        save_dir = os.path.join(os.getcwd(), "qrcodes")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{code}.png")
        img.save(filepath)

        # DB 저장: 신규 등록 또는 재고 업데이트
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO inventory (item_name, item_code, total_stock, created_at) VALUES (?, ?, ?, ?)",
            (name, code, qty, datetime.now().isoformat())
        )
        cur.execute(
            "UPDATE inventory SET total_stock = ? WHERE item_code = ?",
            (qty, code)
        )
        conn.commit()
        conn.close()

        QMessageBox.information(self, "완료", f"QR 코드가 저장되었습니다:\n{filepath}")

    def handle_scan(self):
        """
        카메라로 QR 스캔 → DB에서 해당 물품 조회 → 입/출고 수량 입력 → 재고 업데이트
        """
        data = scan_qr_from_camera()
        if not data:
            QMessageBox.information(self, "알림", "QR 코드 인식에 실패했습니다.")
            return

        code = data.get("item_code")
        name = data.get("item_name")

        # 현재 재고 조회
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT total_stock FROM inventory WHERE item_code = ?", (code,))
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, "오류", f"등록된 물품({code})이 없습니다.")
            conn.close()
            return

        current = row[0]
        # 입/출고 수량 입력 (양수: 입고, 음수: 출고)
        qty, ok = QInputDialog.getInt(
            self, "수량 입력", f"{name} (현재 {current}) - 입고는 양수, 출고는 음수:"
        )
        if not ok:
            conn.close()
            return

        new_stock = current + qty
        cur.execute(
            "UPDATE inventory SET total_stock = ? WHERE item_code = ?",
            (new_stock, code)
        )
        conn.commit()
        conn.close()

        QMessageBox.information(self, "완료", f"{name} 재고가 {new_stock}으로 변경되었습니다.")

    def show_inventory(self):
        """
        전체 재고 현황을 테이블 형태로 다이얼로그에 표시
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT item_name, item_code, total_stock, category FROM inventory")
        rows = cur.fetchall()
        conn.close()

        dlg = QDialog(self)
        dlg.setWindowTitle("재고 현황")
        layout = QVBoxLayout(dlg)
        table = QTableWidget(len(rows), 4)
        table.setHorizontalHeaderLabels(["물품명", "코드", "수량", "분류"])

        for i, (name, code, stock, cat) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(code))
            table.setItem(i, 2, QTableWidgetItem(str(stock)))
            table.setItem(i, 3, QTableWidgetItem(cat or ""))

        layout.addWidget(table)
        dlg.exec()

# 앱 실행 진입점
if __name__ == "__main__":
    # DB 초기화 (data.db 생성 및 테이블 생성)
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
