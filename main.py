# File: smartqr-app/main.py
# File: smartqr-app/main.py

import os
import sys
import json
import PyQt6

# macOS용 Qt 플랫폼 플러그인 경로 지정 (없으면 cocoa 오류)
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

from utils.db.models import init_db, get_connection
from utils.qr_tools import scan_qr_from_camera

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartQR 물품 등록 및 재고관리")
        self.resize(400, 350)

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

        scan_btn = QPushButton("QR 스캔 (재고 입/출고)")
        scan_btn.clicked.connect(self.handle_scan)
        form.addRow(scan_btn)

        view_btn = QPushButton("재고 현황 보기")
        view_btn.clicked.connect(self.show_inventory)
        form.addRow(view_btn)

        # ————— 재고 현황 Excel 내보내기 버튼 —————
        export_inv_btn = QPushButton("재고현황 → Excel")
        export_inv_btn.clicked.connect(self.export_inventory)
        form.addRow(export_inv_btn)

        # ————— 청구서 생성 버튼 —————
        invoice_btn = QPushButton("청구서 생성")
        invoice_btn.clicked.connect(self.generate_invoice)
        form.addRow(invoice_btn)

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

        data = {"item_name": name, "item_code": code, "initial_qty": qty}
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        save_dir = os.path.join(os.getcwd(), "qrcodes")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, f"{code}.png")
        img.save(filepath)

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
        카메라로 QR 스캔 → DB 재고 조회 → 입/출고 수량 입력 → 재고 업데이트
        """
        data = scan_qr_from_camera()
        if not data:
            QMessageBox.information(self, "알림", "QR 코드 인식에 실패했습니다.")
            return

        code = data.get("item_code")
        name = data.get("item_name")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT total_stock FROM inventory WHERE item_code = ?", (code,))
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, "오류", f"등록된 물품({code})이 없습니다.")
            conn.close()
            return
        current = row[0]

        qty, ok = QInputDialog.getInt(
            self,
            "수량 입력",
            f"{name} (현재 {current}) - 입고는 양수, 출고는 음수:"
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

        for i, (n, c, s, cat) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(n))
            table.setItem(i, 1, QTableWidgetItem(c))
            table.setItem(i, 2, QTableWidgetItem(str(s)))
            table.setItem(i, 3, QTableWidgetItem(cat or ""))

        layout.addWidget(table)
        dlg.exec()

    def export_inventory(self):
        """
        inventory 테이블 전체를 Excel(.xlsx) 파일로 내보냅니다.
        """
        from openpyxl import Workbook
        import os
        from datetime import datetime

        # 1) DB에서 전체 재고 데이터 조회
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT item_name, item_code, total_stock, category, created_at FROM inventory"
        )
        rows = cur.fetchall()
        conn.close()

        # 2) 엑셀 워크북/시트 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "재고현황"

        # 3) 헤더 추가
        headers = ["물품명", "코드", "수량", "분류", "등록일시"]
        ws.append(headers)

        # 4) 데이터 추가
        for name, code, stock, cat, created in rows:
            ws.append([name, code, stock, cat or "", created])

        # 5) 저장 경로 설정 및 파일 저장
        save_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"inventory_{timestamp}.xlsx"
        filepath = os.path.join(save_dir, filename)
        wb.save(filepath)

        # 6) 완료 메시지 표시
        QMessageBox.information(
            self,
            "완료",
            f"재고현황이 Excel로 저장되었습니다:\n{filepath}"
        )

    def generate_invoice(self):
        """
        QR 스캔 또는 선택을 통해 청구할 물품과 수량을 입력한 뒤,
        회사 양식의 엑셀 청구서를 생성하고 저장합니다.
        """
        from openpyxl import Workbook
        import os
        from datetime import datetime

        # 1) QR 스캔으로 물품 정보 로드
        data = scan_qr_from_camera()
        if not data:
            QMessageBox.information(self, "알림", "QR 코드 인식에 실패했습니다.")
            return

        code = data.get("item_code")
        name = data.get("item_name")

        # 2) 청구 수량 입력
        qty, ok = QInputDialog.getInt(
            self,
            "청구 수량 입력",
            f"{name} 청구 수량을 입력하세요:"
        )
        if not ok or qty <= 0:
            return

        # 3) DB에 청구 이력 저장
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO request_log (item_code, item_name, quantity_requested, request_date) VALUES (?, ?, ?, ?)",
            (code, name, qty, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # 4) 엑셀 워크북 생성 및 청구서 양식 작성
        wb = Workbook()
        ws = wb.active
        ws.title = "청구서"
        # 헤더 (회사 고정 양식 컬럼 순서에 맞추어 배치)
        headers = ["물품명", "코드", "청구 수량", "작성일시"]
        ws.append(headers)
        ws.append([name, code, qty, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

        # 5) 엑셀 파일 저장
        save_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_{timestamp}.xlsx"
        filepath = os.path.join(save_dir, filename)
        wb.save(filepath)

        # 6) 완료 메시지
        QMessageBox.information(
            self,
            "완료",
            f"청구서 엑셀 파일이 생성되었습니다:\n{filepath}"
        )

# 앱 실행 진입점
if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
