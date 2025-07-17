# coding: utf-8
"""
carla37.py
CARLA 车道保持服务端，Python 3.7 环境下运行。
通过 socket 与 DreamerV3 客户端通信。
"""
import socket
import json
import numpy as np
# import carla  # 需在 Python3.7 环境下安装 carla

class CarlaLaneKeepServer:
    def __init__(self, host='0.0.0.0', port=50037, size=(64, 64), fps=10):
        self.host = host
        self.port = port
        self.size = size
        self.fps = fps
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(1)
        print(f"[CARLA] Listening on {host}:{port}")
        self.conn, _ = self.sock.accept()
        print("[CARLA] Client connected.")
        # self._init_carla()

    def serve(self):
        while True:
            data = self._recv()
            if not data:
                break
            cmd = data.get('cmd')
            if cmd == 'reset':
                obs = self._reset_env()
                self._send({'obs': obs})
            elif cmd == 'step':
                action = data['action']
                obs = self._step_env(action)
                self._send({'obs': obs})

    def _reset_env(self):
        # TODO: 重置 CARLA 环境，返回初始观测
        obs = {
            'image': np.zeros(self.size + (3,), dtype=np.uint8).tolist(),
            'speed': 0.0,
            'done': False
        }
        return obs

    def _step_env(self, action):
        # TODO: 执行动作，返回新观测
        obs = {
            'image': np.zeros(self.size + (3,), dtype=np.uint8).tolist(),
            'speed': float(action.get('acc', 0.0)),
            'done': False
        }
        return obs

    def _send(self, msg):
        self.conn.sendall(json.dumps(msg).encode())

    def _recv(self):
        chunks = []
        while True:
            chunk = self.conn.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                return json.loads(b''.join(chunks).decode())
            except json.JSONDecodeError:
                continue
        return None

    def close(self):
        self.conn.close()
        self.sock.close()

if __name__ == '__main__':
    server = CarlaLaneKeepServer()
    server.serve()
