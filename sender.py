#coding:utf-8
import cv2 as cv
import time
import threading
import socket

# 配置参数
TARGET_IP = '192.168.0.196'
TARGET_PORT = 9999
CHUNK_SIZE = 1024  # 分块大小

# 分辨率档位
RES_LEVELS = [
    (320, 240), # 高
    (240,180),  # 中
    (160,129),  # 低
]
current_res_index = 2 # 初始分辨率档位索引

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

# 测量RTT
def measure_rtt(target_ip, target_port, timeout=0.5):
    socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket.settimeout(timeout)
    probe = b'ping'
    start = time.time()
    try:
        socket.sendto(probe, (target_ip, target_port))
        socket.recvfrom(1024)  # 等待接收响应
        end = time.time()
        return (end - start) * 1000  # 返回RTT，单位为毫秒
    except socket.timeout:
        return float('inf')
    finally:
        socket.close()
# 动态调整分辨率
def adjust_resolution_loop():
    global current_res_index
    while True:
        rtt = measure_rtt(TARGET_IP, TARGET_PORT)
        print(f"[RTT]{rtt:.2f} ms")
        if rtt < 100:
            current_res_index = 0
        elif rtt < 300:
            current_res_index = 1
        else:
            current_res_index = 2
        time.sleep(2)  # 每2秒测量一次RTT

def main():
    print("Sending started")
    cap = cv.VideoCapture(0)
    frame_id = 0  # 帧编号

    # 启动RTT检测线程
    threading.Thread(target=adjust_resolution_loop, daemon=True).start()

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        frame = cv.flip(frame, -1)

        # 动态调整分辨率
        width, height = RES_LEVELS[current_res_index]
        frame = cv.resize(frame, (width, height))

        # 高效编码成JPEG字节流
        _,encoded_img = cv.imencode('.jpg', frame, [int(cv.IMWRITE_JPEG_QUALITY), 80])
        data = encoded_img.tobytes()
        
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