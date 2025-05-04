# File: smartqr-app/utils/qr_tools.py

import cv2
from pyzbar import pyzbar
import json

def scan_qr_from_camera():
    """
    카메라에서 QR 코드를 실시간 스캔하여 JSON 데이터를 반환합니다.
    'q' 키를 누르면 스캔을 종료합니다.
    """
    # 기본 카메라 장치 열기
    cap = cv2.VideoCapture(0)
    result = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 화면에 카메라 피드 표시
        cv2.imshow("QR 스캔 (종료: q)", frame)

        # pyzbar를 사용해 QR 코드 디코딩 시도
        decoded_objects = pyzbar.decode(frame)
        if decoded_objects:
            raw = decoded_objects[0].data.decode("utf-8")
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = None
            break

        # 'q' 키 입력 시 루프 탈출
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 자원 해제 및 창 닫기
    cap.release()
    cv2.destroyAllWindows()
    return result