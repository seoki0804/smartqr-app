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

# ——————— InvoiceDialog class ———————
class InvoiceDialog(QDialog):
    """
    청구서 작성 전용 다이얼로그: 여러 항목을 QR 스캔으로 추가하고
    한 번에 Excel 청구서를 생성합니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("청구서 작성")
        self.resize(500, 400)

        self.invoice_items = []
        layout = QVBoxLayout(self)

        # 테이블: 물품명, 코드, 수량
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["물품명", "코드", "수량"])
        layout.addWidget(self.table)

        # QR 스캔을 통한 항목 추가 버튼
        scan_btn = QPushButton("항목 추가 (QR 스캔)")
        scan_btn.clicked.connect(self.add_item)
        layout.addWidget(scan_btn)

        # ————— 수동 항목 추가 버튼 —————
        manual_btn = QPushButton("수동 항목 추가")
        manual_btn.clicked.connect(self.manual_add_item)
        layout.addWidget(manual_btn)

        # ————— 선택 항목 삭제 버튼 —————
        delete_btn = QPushButton("항목 삭제")
        delete_btn.clicked.connect(self.delete_selected_item)
        layout.addWidget(delete_btn)

        # 청구서 생성 버튼
        gen_btn = QPushButton("청구서 생성")
        gen_btn.clicked.connect(self.generate_invoice)
        layout.addWidget(gen_btn)

    def add_item(self):
        data = scan_qr_from_camera()
        if not data:
            QMessageBox.information(self, "알림", "QR 인식 실패")
            return
        name = data.get("item_name")
        code = data.get("item_code")
        qty, ok = QInputDialog.getInt(self, "수량 입력", f"{name} 수량:")
        if not ok or qty <= 0:
            return
        self.invoice_items.append({"item_name": name, "item_code": code, "qty": qty})
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(code))
        self.table.setItem(row, 2, QTableWidgetItem(str(qty)))

    def generate_invoice(self):
        if not self.invoice_items:
            QMessageBox.warning(self, "오류", "청구할 항목이 없습니다.")
            return
        from openpyxl import Workbook
        now_iso = datetime.now().isoformat()
        conn = get_connection(); cur = conn.cursor()
        for item in self.invoice_items:
            cur.execute(
                "INSERT INTO request_log (item_code, item_name, quantity_requested, request_date) VALUES (?, ?, ?, ?)",
                (item["item_code"], item["item_name"], item["qty"], now_iso)
            )
        conn.commit(); conn.close()
        wb = Workbook(); ws = wb.active; ws.title = "청구서"
        ws.append(["물품명", "코드", "청구수량", "작성일시"])
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in self.invoice_items:
            ws.append([item["item_name"], item["item_code"], item["qty"], ts])
        save_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(save_dir, exist_ok=True)
        fname = f"invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(save_dir, fname)
        wb.save(filepath)
        QMessageBox.information(self, "완료", f"청구서 엑셀 파일 생성:\n{filepath}")
        self.invoice_items.clear()
        self.table.setRowCount(0)

    def manual_add_item(self):
        """
        기존 등록된 물품을 드롭다운에서 선택해
        청구 리스트에 수동으로 추가합니다.
        """
        # 1) DB에서 물품 목록 조회
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT item_name, item_code FROM inventory")
        items = cur.fetchall()
        conn.close()

        if not items:
            QMessageBox.information(self, "알림", "등록된 물품이 없습니다.")
            return

        # 2) 선택지 생성
        choices = [f"{n} ({c})" for n, c in items]
        choice, ok = QInputDialog.getItem(
            self,
            "물품 선택",
            "추가할 물품을 선택하세요:",
            choices,
            editable=False
        )
        if not ok:
            return

        # 3) 선택된 인덱스로 원본 데이터 가져오기
        idx = choices.index(choice)
        name, code = items[idx]

        # 4) 청구 수량 입력
        qty, ok = QInputDialog.getInt(
            self,
            "수량 입력",
            f"{name} 청구 수량을 입력하세요:"
        )
        if not ok or qty <= 0:
            return

        # 5) 리스트 및 테이블에 추가
        self.invoice_items.append({"item_name": name, "item_code": code, "qty": qty})
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(code))
        self.table.setItem(row, 2, QTableWidgetItem(str(qty)))

    def delete_selected_item(self):
        """
        테이블에서 선택된 행을 삭제하고,
        invoice_items 리스트에서도 동일 인덱스의 항목을 제거합니다.
        """
        # 선택된 행 인덱스 목록 가져오기
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택하세요.")
            return

        # 인덱스를 내림차순으로 정렬해 삭제 (인덱스 밀림 방지)
        rows = sorted([r.row() for r in selected_rows], reverse=True)
        for row_index in rows:
            # 리스트에서도 제거
            del self.invoice_items[row_index]
            # 테이블에서도 제거
            self.table.removeRow(row_index)

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

        # ————— 재고 전체 삭제 버튼 —————
        clear_btn = QPushButton("재고 전체 삭제")
        clear_btn.clicked.connect(self.clear_inventory)
        form.addRow(clear_btn)

        # ————— 청구서 생성 버튼 —————
        invoice_btn = QPushButton("청구서 작성 창 열기")
        invoice_btn.clicked.connect(self.open_invoice_dialog)
        form.addRow(invoice_btn)

        # ————— 청구 이력 보기 버튼 —————
        history_btn = QPushButton("청구 이력 보기")
        history_btn.clicked.connect(self.show_request_log)
        form.addRow(history_btn)

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


    def open_invoice_dialog(self):
        dlg = InvoiceDialog(self)
        dlg.exec()

    def show_request_log(self):
        """
        request_log 테이블의 모든 청구 이력을 테이블 형태로 다이얼로그에 표시합니다.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT item_name, item_code, quantity_requested, request_date FROM request_log"
        )
        rows = cur.fetchall()
        conn.close()

        dlg = QDialog(self)
        dlg.setWindowTitle("청구 이력")
        layout = QVBoxLayout(dlg)
        table = QTableWidget(len(rows), 4)
        table.setHorizontalHeaderLabels(["물품명", "코드", "수량", "청구일시"])

        for i, (name, code, qty, date) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(code))
            table.setItem(i, 2, QTableWidgetItem(str(qty)))
            table.setItem(i, 3, QTableWidgetItem(date))

        layout.addWidget(table)
        dlg.exec()

    def clear_inventory(self):
        """
        inventory 테이블의 모든 데이터를 삭제합니다.
        """
        reply = QMessageBox.question(
            self,
            "경고",
            "정말 모든 재고를 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM inventory")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "완료", "모든 재고가 삭제되었습니다.")

# 앱 실행 진입점
if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())