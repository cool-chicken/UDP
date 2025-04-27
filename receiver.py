import time
from multiprocessing import Process, Queue, set_start_method
import socket
import cv2 as cv
from collections import defaultdict
import numpy as np

CHUNK_SIZE = 1024
WIDTH, HEIGHT = 320, 240
PAUSE_DURATION = 10  # 窗口关闭后暂停接收的时间（秒）

try:
    set_start_method('spawn')
except RuntimeError:
    pass


def assemble_frame(chunks_dict, total_chunks):
    """拼接完整帧，支持一块丢失恢复（XOR校验）"""
    missing = [i for i in range(total_chunks) if i not in chunks_dict]
    if len(missing) == 1:
        missing_id = missing[0]
        recovered = bytearray(CHUNK_SIZE)
        try:
            for i in range(total_chunks):
                if i != missing_id:
                    chunk = chunks_dict[i]
                    for j in range(len(chunk)):
                        recovered[j] ^= chunk[j]
            chunks_dict[missing_id] = bytes(recovered)
        except Exception as e:
            print(f"[恢复失败] {e}")
            return None
    elif len(missing) > 1:
        return None

    try:
        return b''.join(chunks_dict[i] for i in range(total_chunks))
    except:
        return None


def per_ip_process(ip, q: Queue, exit_flag: Queue):
    """每个 IP 创建一个 OpenCV 窗口显示视频"""
    print(f"[✓] 进程启动：{ip}")
    frame_buffer = defaultdict(dict)
    last_frame_time = time.time()
    fps = 0

    window_name = f'视频源 {ip}'
    cv.namedWindow(window_name, cv.WINDOW_NORMAL)  # 叉叉关闭窗口

    while True:
        try:
            data = q.get(timeout=0.02)
            if data == b'__exit__':
                print(f"[!] 关闭窗口 {ip}")
                break

            frame_id = int.from_bytes(data[0:2], 'big')
            chunk_id = data[2]
            total_chunks = data[3]
            chunk_data = data[4:]

            frame_buffer[frame_id][chunk_id] = chunk_data

            if len(frame_buffer[frame_id]) == total_chunks:
                raw = assemble_frame(frame_buffer[frame_id], total_chunks)
                frame_buffer.pop(frame_id, None)

                if raw:
                    img = cv.imdecode(np.frombuffer(raw, np.uint8), cv.IMREAD_COLOR)
                    if img is None:
                        print(f"[×] 解码失败 frame {frame_id}")
                        continue
                    if img.shape[:2] != (HEIGHT, WIDTH):
                        img = cv.resize(img, (WIDTH, HEIGHT))

                    # FPS 计算
                    now = time.time()
                    fps = 1.0 / (now - last_frame_time)
                    last_frame_time = now
                    cv.putText(img, f"FPS: {fps:.1f}", (10, 20), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    # 显示窗口
                    cv.imshow(window_name, img)

                    key = cv.waitKey(1) & 0xFF
                    window_status = cv.getWindowProperty(window_name, cv.WND_PROP_VISIBLE)

                    # 检测是否需要退出
                    if key == ord('q') or key == 27 or window_status < 1:
                        print(f"[×] {ip} 窗口关闭（按键或点击×）")
                        exit_flag.put(ip)  # 向主进程发送关闭信号
                        cv.destroyWindow(window_name)  # 销毁窗口
                        break


                    if cv.getWindowProperty(window_name, cv.WND_PROP_VISIBLE) < 1:
                        print(f"[×] {ip} 窗口已关闭")
                        exit_flag.put(ip)  # 向主进程发送关闭信号
                        cv.destroyWindow(window_name)  # 销毁窗口
                        break

        except Exception:
            continue

    cv.destroyAllWindows()


def dispatch_thread():
    """主进程负责接收 UDP 数据并分发到子进程队列"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 12345))
    s.settimeout(1)

    ip_queues = {}
    ip_processes = {}
    exit_flag = Queue()
    paused_ips = {}  # 记录暂停的 IP 和恢复时间

    print("😆😆😆接收器启动，等待客户端发送视频...") #😆😆😆双进程启动！！！

    try:
        while True:
            try:
                data, addr = s.recvfrom(CHUNK_SIZE + 4)
                ip = addr[0]

                # 检查该 IP 是否在暂停列表中
                if ip in paused_ips:
                    if time.time() < paused_ips[ip]:
                        continue  # 跳过该 IP 的数据包
                    else:
                        del paused_ips[ip]  # 移除暂停状态

                if data == b'ping':
                    s.sendto(b'pong', addr)
                    continue

                if ip not in ip_queues:
                    print(f"[+] 新客户端接入：{ip}")
                    q = Queue()
                    p = Process(target=per_ip_process, args=(ip, q, exit_flag))
                    p.start()
                    ip_queues[ip] = q
                    ip_processes[ip] = p

                ip_queues[ip].put(data)

            except socket.timeout:
                continue
            except KeyboardInterrupt:
                print("[!] 主线程中断，清理资源")
                break
            except Exception as e:
                print(f"[错误] {e}")

            # 检查是否所有窗口都已关闭
            while not exit_flag.empty():
                closed_ip = exit_flag.get()
                print(f"[✓] {closed_ip} 已关闭窗口")
                ip_queues[closed_ip].put(b'__exit__')  # 向进程发送退出信号
                ip_processes[closed_ip].join()  # 等待子进程退出
                del ip_queues[closed_ip]
                del ip_processes[closed_ip]

                # 添加暂停时间
                paused_ips[closed_ip] = time.time() + PAUSE_DURATION
                print(f"[!] 暂停接收来自 {closed_ip} 的数据 {PAUSE_DURATION} 秒")

            if not ip_processes:
                print("所有窗口已关闭，退出主线程...")
                break

    finally:
        cv.destroyAllWindows()

if __name__ == '__main__':
    dispatch_thread()