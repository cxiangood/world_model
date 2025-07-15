# Python 3.11
import zmq
import numpy as np
import gymnasium as gym

class CarlaRemoteEnv(gym.Env):
    def __init__(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5555")

        obs = self.reset()
        self.obs_space = gym.spaces.Box(low=0, high=255, shape=np.array(obs).shape, dtype=np.float32)
        self.act_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)

    def reset(self):
        self.socket.send_json({"cmd": "reset"})
        response = self.socket.recv_json()
        return np.array(response["obs"], dtype=np.float32)

    def step(self, action):
        self.socket.send_json({"cmd": "step", "action": action.tolist()})
        response = self.socket.recv_json()
        obs = np.array(response["obs"], dtype=np.float32)
        return obs, response["reward"], response["done"], response["info"]
