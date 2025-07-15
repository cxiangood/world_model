#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import zmq
import time
import json
import numpy as np
import gymnasium as gym
from typing import Dict, Any, Tuple, Optional

# 尝试导入 gym_carla，如果不存在则使用自定义环境
try:
    import gymnasium as gym_carla
except ImportError:
    print("⚠️ 未找到 gym_carla，将使用自定义环境")
    # 这里可以添加自定义环境的代码

class CarlaServer:
    """CARLA服务器，通过ZMQ接收命令并与CARLA环境交互"""
    
    def __init__(self, port: int = 5555, env_id: str = "carla_rl-gym-v0"):
        self.port = port
        self.env_id = env_id
        self.env = None
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{self.port}")
        print(f"🚗 CARLA服务器启动，监听端口 {self.port}...")
    
    def init_env(self) -> None:
        """初始化CARLA环境"""
        print(f"🔧 初始化环境: {self.env_id}")
        try:
            self.env = gym.make(self.env_id)
            print("✅ 环境初始化成功")
        except Exception as e:
            print(f"❌ 环境初始化失败: {e}")
            raise
    
    def handle_request(self) -> None:
        """处理客户端请求"""
        while True:
            try:
                # 接收请求
                request = self.socket.recv_json()
                cmd = request.get("cmd")
                params = request.get("params", {})
                
                # 处理命令
                response = {"status": "success"}
                
                if cmd == "init":
                    self.init_env()
                    response["message"] = "环境初始化完成"
                
                elif cmd == "reset":
                    if not self.env:
                        self.init_env()
                    obs = self.env.reset()
                    response["obs"] = self._serialize_obs(obs)
                
                elif cmd == "step":
                    if not self.env:
                        raise RuntimeError("环境未初始化，请先调用init")
                    
                    action = np.array(params.get("action", []))
                    obs, reward, done, info = self.env.step(action)
                    
                    response.update({
                        "obs": self._serialize_obs(obs),
                        "reward": float(reward),
                        "done": bool(done),
                        "info": info
                    })
                
                elif cmd == "close":
                    if self.env:
                        self.env.close()
                    response["message"] = "环境已关闭"
                    break
                
                elif cmd == "ping":
                    response["message"] = "pong"
                
                else:
                    response = {"status": "error", "message": f"未知命令: {cmd}"}
                
                # 发送响应
                self.socket.send_json(response)
            
            except Exception as e:
                error_msg = f"处理请求时出错: {str(e)}"
                print(error_msg)
                self.socket.send_json({"status": "error", "message": error_msg})
    
    def _serialize_obs(self, obs: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """序列化观测数据为JSON可传输格式"""
        serialized = {}
        for k, v in obs.items():
            if isinstance(v, np.ndarray):
                # 对于图像数据，可以考虑压缩以提高传输效率
                serialized[k] = v.tolist()
            else:
                serialized[k] = v
        return serialized
    
    def run(self) -> None:
        """运行服务器"""
        try:
            self.handle_request()
        except KeyboardInterrupt:
            print("🔴 服务器被用户中断")
        finally:
            if self.env:
                self.env.close()
            self.socket.close()
            self.context.term()
            print("🛑 服务器已关闭")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CARLA服务器")
    parser.add_argument("--port", type=int, default=5555, help="ZMQ通信端口")
    parser.add_argument("--env-id", type=str, default="carla_rl-gym-v0", help="环境ID")
    args = parser.parse_args()
    
    server = CarlaServer(port=args.port, env_id=args.env_id)
    server.run()