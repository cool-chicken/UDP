#coding:utf-8
import cv2 as cv
import time
import threading
import socket
import os

# 配置参数
TARGET_IP = '10.198.172.57'  # 这里需要填写接收端IP地址
TARGET_PORT = 12345
CHUNK_SIZE = 1024  # 分块大小

# 分辨率档位
RES_LEVELS = [
    (320, 240), # 高
    (240,180),  # 中
    (160,129),  # 低
]
current_res_index = 2 # 初始分辨率档位索引

def send_frame_in_chunks(sock, frame_data, addr, frame_id):
    total_chunks = (len(frame_data) - 1) // CHUNK_SIZE + 1
    chunks = []  # 缓存所有分块数据
    parity_chunk = bytearray(CHUNK_SIZE)  # 奇偶校验块初始化

    for i in range(total_chunks):
        start = i * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk_data = frame_data[start:end]
        # 包结构：帧ID(2B) + 块编号(1B) + 总块数(1B) + 数据
        header = frame_id.to_bytes(2, 'big') + bytes([i]) + bytes([total_chunks + 1])  # +1 表示包含校验块
        chunks.append(header + chunk_data)
        sock.sendto(chunks[-1], addr)

        # 更新奇偶校验块
        for j in range(len(chunk_data)):
            parity_chunk[j] ^= chunk_data[j]

    # 发送奇偶校验块
    parity_header = frame_id.to_bytes(2, 'big') + bytes([total_chunks]) + bytes([total_chunks + 1])
    sock.sendto(parity_header + parity_chunk, addr)

# 测量RTT
def measure_rtt(target_ip, target_port, timeout=0.5):   #timeout是0.5s会不会太短
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 避免变量名冲突
    udp_socket.settimeout(timeout)
    probe = b'ping'
    start = time.time()
    try:
        udp_socket.sendto(probe, (target_ip, target_port))
        udp_socket.recvfrom(1024)  # 等待接收响应
        end = time.time()
        return (end - start) * 1000  # 返回RTT，单位为毫秒
    except socket.timeout:
        return float('inf')
    finally:
        udp_socket.close()
# 动态调整分辨率
def adjust_resolution_loop():
    global current_res_index
    timeout_count = 0  # 超时计数器

    while True:
        rtt = measure_rtt(TARGET_IP, TARGET_PORT)
        print(f"[RTT] {rtt:.2f} ms")

        if rtt == float('inf'):  # 检测到超时
            timeout_count += 1
            print(f"[警告] RTT 超时次数：{timeout_count}")
            if timeout_count >= 5:  # 连续超时 5 次
                print("[错误] 连续超时 5 次，发送端即将退出...")
                os._exit(1)# 退出程序
        else:
            timeout_count = 0  # 如果 RTT 正常，重置计数器

        # 根据 RTT 动态调整分辨率
        if rtt < 100:
            current_res_index = 0
        elif rtt < 300:
            current_res_index = 1
        else:
            current_res_index = 2

        time.sleep(2)  # 每 2 秒测量一次 RTT


def main():
    print("Sending started")
    cap = cv.VideoCapture(0)
    frame_id = 0  # 帧编号

    # 启动RTT检测线程
    threading.Thread(target=adjust_resolution_loop, daemon=True).start()

    fps = 30  # 设置帧率
    frame_interval = 1 / fps
    last_frame_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        # frame = cv.flip(frame, -1)

        # 动态调整分辨率
        width, height = RES_LEVELS[current_res_index]
        frame = cv.resize(frame, (width, height))

        # 高效编码成JPEG字节流
        _,encoded_img = cv.imencode('.jpg', frame, [int(cv.IMWRITE_JPEG_QUALITY), 98])
        data = encoded_img.tobytes()
        
        # 启动 UDP 发送线程
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        t = threading.Thread(target=send_frame_in_chunks, args=(sock, data, (TARGET_IP, TARGET_PORT), frame_id))
        t.start()
        frame_id = (frame_id + 1) % 65536  # 避免帧编号溢出

        # 控制帧率
        elapsed = time.time() - last_frame_time
        if elapsed < frame_interval:
            time.sleep(frame_interval - elapsed)
        last_frame_time = time.time()

        if cv.waitKey(10) & 0xff == ord('q'):
            break

    cap.release()
    cv.destroyAllWindows()

main()