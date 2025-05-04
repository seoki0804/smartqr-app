# File: smartqr-app/utils/qr_tools.py

import cv2
from pyzbar import pyzbar
import json

def scan_qr_from_camera():
    """
    카메라에서 QR 코드를 실시간 스캔하여,
    JSON으로 인코딩된 데이터를 파싱해 반환합니다.
    사용자가 'q' 키를 누르면 스캔을 중단하고 종료합니다.
    """
    # 1) 디폴트 카메라 열기 (0번 디바이스)
    cap = cv2.VideoCapture(0)
    result = None

    while True:
        ret, frame = cap.read()
        if not ret:
            # 카메라 프레임을 못 읽어오면 반복 종료
            break

        # 2) 프레임을 화면에 표시
        cv2.imshow("QR 스캔 (종료: q)", frame)

        # 3) pyzbar로 바코드/QR 디코딩 시도
        decoded_objects = pyzbar.decode(frame)
        if decoded_objects:
            # 첫 번째 QR 데이터만 처리
            raw = decoded_objects[0].data.decode("utf-8")
            try:
                # JSON 문자열을 파싱
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = None
            break

        # 4) 키 입력 대기: 'q' 누르면 루프 탈출
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 5) 카메라 자원 해제 및 모든 창 닫기
    cap.release()
    cv2.destroyAllWindows()
    return result