#coding=utf-8
import socket
import pygame
import time
from collections import defaultdict
import numpy as np
import cv2 as cv  # 添加 OpenCV 以解码 JPEG 数据

CHUNK_SIZE = 1024  # 确保两端的值一致
        


# 初始化 Pygame 界面
pygame.init()
pygame.display.set_caption('UDP 视频接收')

WIDTH, HEIGHT = 320, 240
display = pygame.display.set_mode((WIDTH, HEIGHT))
WHITE, BLACK = (255,255,255), (0,0,0)
# font = pygame.font.Font('C:/Windows/Fonts/comici.ttf', 20)
font = pygame.font.Font('freesansbold.ttf', 32)
textRect = font.render('FPS', True, BLACK, WHITE).get_rect(center=(270, 10))

# UDP 接收设置
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('10.198.33.64', 9999))
s.settimeout(1)

# 帧缓存和计时器
frame_buffer = defaultdict(dict)
last_complete_frame = None
frame_rate = 0
start = time.perf_counter()

# **TODO: 重新组装帧**
# def assemble_frame(chunks_dict, total_chunks):
#     """
#     用于从分块数据中重新组装帧。确保所有块都接收完整才进行拼接。
#     如果缺失块或顺序不对，这里可以返回 None，表示帧不完整。
#     """
#     frame_data = b''.join(chunks_dict[i] for i in range(total_chunks) if i in chunks_dict)
#     return frame_data if len(chunks_dict) == total_chunks else None

def assemble_frame(chunks_dict, total_chunks):
    """
    从分块数据中重新组装帧。如果有丢失的块，尝试使用奇偶校验块恢复。
    """
    missing_chunks = [i for i in range(total_chunks) if i not in chunks_dict]

    # 如果只有一个块丢失，尝试恢复
    if len(missing_chunks) == 1:
        missing_chunk_id = missing_chunks[0]
        recovered_chunk = bytearray(CHUNK_SIZE)
        for i in range(total_chunks):
            if i != missing_chunk_id:
                chunk_data = chunks_dict[i]
                for j in range(len(chunk_data)):
                    recovered_chunk[j] ^= chunk_data[j]
        chunks_dict[missing_chunk_id] = bytes(recovered_chunk)

    # 如果仍有丢失块，返回 None
    if len(chunks_dict) < total_chunks:
        return None

    # 拼接完整帧
    frame_data = b''.join(chunks_dict[i] for i in range(total_chunks))
    return frame_data

running = True
while running:
    try:
        # 接收数据包，获取帧信息
        data, addr = s.recvfrom(1024 + 4)
        if data == b'ping':
            s.sendto(b'pong', addr)
            continue

        frame_id = int.from_bytes(data[0:2], 'big')
        chunk_id = data[2]
        total_chunks = data[3]
        chunk_data = data[4:]

        # 保存数据块到缓存中
        frame_buffer[frame_id][chunk_id] = chunk_data

        # **TODO: 拼接完整帧**
        # 如果当前帧的数据全部接收完，进行拼接

        # 如果当前帧的数据全部接收完，进行拼接
        if len(frame_buffer[frame_id]) == total_chunks:
            assembled = assemble_frame(frame_buffer[frame_id], total_chunks)
            if assembled:
                # 解码 JPEG 数据
                decoded_frame = cv.imdecode(np.frombuffer(assembled, np.uint8), cv.IMREAD_COLOR)
                if decoded_frame is None:
                    print(f"帧 {frame_id} 解码失败")
                    continue
        
                # 检查解码后的分辨率是否匹配
                if decoded_frame.shape[:2] != (HEIGHT, WIDTH):
                    print(f"帧 {frame_id} 分辨率不匹配，期望 {(HEIGHT, WIDTH)}，实际 {decoded_frame.shape[:2]}")
                    decoded_frame = cv.resize(decoded_frame, (WIDTH, HEIGHT))  # 调整到期望分辨率
        
                # 转换为 RGB 格式
                decoded_frame = cv.cvtColor(decoded_frame, cv.COLOR_BGR2RGB)
        
                # 转换为 Pygame 图像
                img = pygame.image.frombuffer(decoded_frame.tobytes(), (WIDTH, HEIGHT), "RGB")
                last_complete_frame = img
        
                # 删除已处理的帧缓存
                if frame_id in frame_buffer:
                    frame_buffer.pop(frame_id)
                    print(f"帧 {frame_id} 已成功删除")
                else:
                    print(f"警告：帧 {frame_id} 不存在，无法删除")
            else:
                print(f"帧 {frame_id} 丢失，无法恢复")
    except socket.timeout:
        pass

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    display.fill(WHITE)

    # **TODO: 丢包隐性恢复**
    # 如果帧丢失，显示上一帧
    if last_complete_frame:
        display.blit(last_complete_frame, (0, 0))

    # 更新 FPS
    frame_rate += 1
    if time.perf_counter() - start > 1:
        fps_text = font.render("FPS: " + str(frame_rate), True, BLACK, WHITE)
        frame_rate = 0
        start = time.perf_counter()
    display.blit(fps_text, textRect)

    pygame.display.update()
    pygame.time.Clock().tick(60)

pygame.quit()