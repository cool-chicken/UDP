#coding:utf-8
import pygame
import cv2 as cv
import time
import threading
import socket

pygame.init()

# 配置参数
TARGET_IP = '192.168.0.196'
TARGET_PORT = 9999
CHUNK_SIZE = 1024  # 分块大小
FRAME_WIDTH, FRAME_HEIGHT = 160, 120  # 初始分辨率

# 分包函数
def send_frame_in_chunks(sock, frame_data, addr, frame_id):
    total_chunks = (len(frame_data) - 1) // CHUNK_SIZE + 1
    for i in range(total_chunks):
        start = i * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk_data = frame_data[start:end]
        # 包结构：帧ID(2B) + 块编号(1B) + 总块数(1B) + 数据
        header = frame_id.to_bytes(2, 'big') + bytes([i]) + bytes([total_chunks])
        sock.sendto(header + chunk_data, addr)

def main():
    print("Sending started")
    cap = cv.VideoCapture(0)
    frame_id = 0  # 帧编号

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv.flip(frame, -1)

        # **TODO: 动态调整分辨率（根据网络延迟等因素，调整帧率、分辨率等）**
        # [目前设定为固定分辨率，动态调整分辨率的代码可以根据网络质量或延迟进行调整]
        frame = cv.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # 编码成字符串
        cv.imwrite("frame.jpg", frame)
        img = pygame.image.load("frame.jpg")
        data = pygame.image.tostring(img, "RGB")

        # 启动 UDP 发送线程
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        t = threading.Thread(target=send_frame_in_chunks, args=(sock, data, (TARGET_IP, TARGET_PORT), frame_id))
        t.start()
        frame_id = (frame_id + 1) % 65536  # 避免帧编号溢出

        if cv.waitKey(10) & 0xff == ord('q'):
            break

    cap.release()
    cv.destroyAllWindows()

main()