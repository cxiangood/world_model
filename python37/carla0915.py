import socket
import json
import time
import numpy as np

try:
    import carla
except ImportError:
    carla = None

HOST = '127.0.0.1'
PORT = 50037
IMAGE_SIZE = (64, 64)
FPS = 10

class CarlaLaneKeepingServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(1)
        self.vehicle = None
        self.world = None
        self.camera_sensor = None
        self.last_image = None
        self.done = True
        self._connect_to_carla()
        print(f"[Carla0915] Server started at {host}:{port}")

    def _connect_to_carla(self):
        self.client_carla = carla.Client('localhost', 2000)
        self.client_carla.set_timeout(10.0)
        self.world = self.client_carla.get_world()
        self.blueprint_library = self.world.get_blueprint_library()

    def _spawn_vehicle(self):
        vehicle_bp = self.blueprint_library.filter('vehicle.*')[0]
        spawn_point = self.world.get_map().get_spawn_points()[0]
        self.vehicle = self.world.try_spawn_actor(vehicle_bp, spawn_point)
        self.vehicle.set_autopilot(False)
        spectator = self.world.get_spectator()
        transform = self.vehicle.get_transform()
        back_vec = carla.Location(x=-8, y=0)
        cam_location = transform.location + back_vec + carla.Location(z=8)
        cam_rotation = carla.Rotation(pitch=-60, yaw=transform.rotation.yaw)
        spectator.set_transform(carla.Transform(cam_location, cam_rotation))

    def _setup_camera(self):
        camera_bp = self.blueprint_library.find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', str(IMAGE_SIZE[1]))
        camera_bp.set_attribute('image_size_y', str(IMAGE_SIZE[0]))
        camera_bp.set_attribute('fov', '90')
        camera_transform = carla.Transform(carla.Location(x=2.0, z=1.4), carla.Rotation(pitch=-15))
        self.camera_sensor = self.world.spawn_actor(camera_bp, camera_transform, attach_to=self.vehicle)
        self.camera_sensor.listen(self._on_camera_data)

    def _on_camera_data(self, image):
        array = np.frombuffer(image.raw_data, dtype=np.uint8)
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3]
        self.last_image = array.tolist()

    def reset(self):
        if self.vehicle:
            self.vehicle.destroy()
        if self.camera_sensor:
            self.camera_sensor.destroy()
        self._spawn_vehicle()
        self._setup_camera()
        self.done = False
        time.sleep(0.2)
        return self._get_obs()

    def step(self, action):
        steer = float(np.clip(action.get('steer', 0.0), -1.0, 1.0))
        acc = float(np.clip(action.get('acc', 0.0), -1.0, 1.0))
        throttle = acc if acc > 0 else 0.0
        brake = -acc if acc < 0 else 0.0
        control = carla.VehicleControl()
        control.steer = steer
        control.throttle = throttle
        control.brake = brake
        self.vehicle.apply_control(control)
        self.world.tick()
        time.sleep(1.0 / FPS)
        return self._get_obs()

    def _get_obs(self):
        image = self.last_image if self.last_image is not None else [[0]*3]*IMAGE_SIZE[0]*IMAGE_SIZE[1]
        velocity = self.vehicle.get_velocity()
        speed = float(np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2))
        obs = {
            'image': image,
            'speed': speed,
            'done': self.done
        }
        return obs

    def serve(self):
        while True:
            print("[Carla0915] Waiting for DreamerV3 client...")
            conn, addr = self.server.accept()
            print(f"[Carla0915] Connected by {addr}")
            try:
                while True:
                    data = conn.recv(40960)
                    if not data:
                        break
                    msg = json.loads(data.decode())
                    if msg['cmd'] == 'reset':
                        obs = self.reset()
                        conn.sendall(json.dumps({'obs': obs}).encode())
                    elif msg['cmd'] == 'step':
                        obs = self.step(msg['action'])
                        conn.sendall(json.dumps({'obs': obs}).encode())
                    else:
                        conn.sendall(json.dumps({'error': 'Unknown command'}).encode())
            except Exception as e:
                print(f"[Carla0915] Client error: {e}")
            finally:
                conn.close()

if __name__ == '__main__':
    server = CarlaLaneKeepingServer(HOST, PORT)
    server.serve()
