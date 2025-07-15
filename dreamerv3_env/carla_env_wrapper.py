import sys
import os

print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("sys.path:", sys.path)
print("Current working directory:", os.getcwd())

from gymnasium.envs.registration import register

# 注册 Carla 环境为 Gym 格式，供 DreamerV3 使用
register(
    id='carla_rl-gym-v0',
    entry_point='carla_gym.src.env.environment:CarlaEnv',
)

# DreamerV3 接入用的包装类
def make_carla_env():
    import gymnasium as gym
    env = gym.make(
        'carla_rl-gym-v0',
        time_limit=300,
        initialize_server=False,
        random_weather=True,
        synchronous_mode=True,
        continuous=False,
        show_sensor_data=False,
        random_traffic=True
    )
    return env
