import gymnasium as gym
print([spec for spec in gym.registry if 'carla' in spec])
# 应输出: ['carla_rl-gym-v0']