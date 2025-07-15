# Python 3.7
import zmq
import gymnasium as gym
import gymnasium as gym_carla
import json
import numpy as np

# 初始化 CARLA 环境
params = {
    "number_of_vehicles": 20,
    "number_of_walkers": 10,
    "display_size": 256,
    "discrete": False,
    "town": "Town03",
    "max_time_episode": 1000,
    "max_past_step": 3,  # 补充: 历史状态存储步数，用于多帧堆叠
    "dt": 0.1,           # 补充：仿真时间步长
    "task_mode": "random",  # 补充：任务模式（random/roundabout等）
    "max_waypt": 100,      # 补充：最大路点数量
    "obs_range": 50,       # 补充：观测范围（米）
    "lidar_bin": 1,        # 补充：激光雷达分箱大小
    "d_behind": 10,        # 补充：车辆后方观测距离
    "out_lane_thres": 2.0, # 补充：偏离车道阈值
    "desired_speed": 20,   # 补充：期望速度（m/s）
    "max_ego_spawn_times": 20, # 补充：最大生成尝试次数
    "display_route": True, # 补充：是否显示路线
    "port": 2000,          # 补充：CARLA服务器端口
    "continuous_accel_range": [-5, 5],  # 补充：连续加速度范围
    "continuous_steer_range": [-1, 1],  # 补充：连续转向范围
    "discrete_acc": [0.0, 1.0],         # 补充：离散加速度选项
    "discrete_steer": [-0.5, 0.0, 0.5] , # 补充：离散转向选项
    "ego_vehicle_filter": "vehicle.tesla.model3", 
}
env = gym.make('carla-v0', params=params)
obs = env.reset()

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    msg = socket.recv_json()
    
    if msg["cmd"] == "reset":
        obs = env.reset()
        socket.send_json({"obs": obs.tolist()})
    elif msg["cmd"] == "step":
        action = np.array(msg["action"])
        obs, reward, done, info = env.step(action)
        socket.send_json({
            "obs": obs.tolist(),
            "reward": reward,
            "done": done,
            "info": info
        })
