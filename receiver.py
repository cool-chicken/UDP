#coding=utf-8
import socket
import pygame
import time
from collections import defaultdict
import numpy as np

# 初始化 Pygame 界面
pygame.init()
pygame.display.set_caption('UDP 视频接收')

WIDTH, HEIGHT = 320, 240
display = pygame.display.set_mode((WIDTH, HEIGHT))
WHITE, BLACK = (255,255,255), (0,0,0)
font = pygame.font.Font('C:/Windows/Fonts/comici.ttf', 20)
textRect = font.render('FPS', True, BLACK, WHITE).get_rect(center=(270, 10))

# UDP 接收设置
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('192.168.0.196', 9999))
s.settimeout(1)

# 帧缓存和计时器
frame_buffer = defaultdict(dict)
last_complete_frame = None
frame_rate = 0
start = time.perf_counter()

# **TODO: 重新组装帧**
def assemble_frame(chunks_dict, total_chunks):
    """
    用于从分块数据中重新组装帧。确保所有块都接收完整才进行拼接。
    如果缺失块或顺序不对，这里可以返回 None，表示帧不完整。
    """
    frame_data = b''.join(chunks_dict[i] for i in range(total_chunks) if i in chunks_dict)
    return frame_data if len(chunks_dict) == total_chunks else None

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
        if len(frame_buffer[frame_id]) == total_chunks:
            assembled = assemble_frame(frame_buffer[frame_id], total_chunks)
            if assembled:
                img = pygame.image.frombuffer(assembled, (160, 120), "RGB")
                last_complete_frame = img
                frame_buffer.pop(frame_id)  # 删除已处理的帧缓存

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