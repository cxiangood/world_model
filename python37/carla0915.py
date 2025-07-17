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
    def _follow_vehicle(self):
        import math
        try:
            spectator = self.world.get_spectator()
            transform = self.vehicle.get_transform()
            yaw = math.radians(transform.rotation.yaw)
            dx = 8 * math.cos(yaw)
            dy = 8 * math.sin(yaw)
            cam_location = transform.location + carla.Location(x=dx, y=dy, z=2)
            cam_rotation = carla.Rotation(pitch=0, yaw=transform.rotation.yaw)
            spectator.set_transform(carla.Transform(cam_location, cam_rotation))
            print(f"[Carla0915] Spectator set to {cam_location} {cam_rotation}")
        except Exception as e:
            print(f"[Carla0915] Spectator follow failed: {e}")
    def _init_stuck_detector(self):
        self._stuck_steps = 0
        self._last_location = None

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
        self._init_stuck_detector()
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
        self._follow_vehicle()

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
        self._init_stuck_detector()
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
        # 卡死检测
        obs = self._get_obs()
        speed = obs['speed']
        loc = self.vehicle.get_location()
        if self._last_location is not None:
            dist = loc.distance(self._last_location)
        else:
            dist = 0
        self._last_location = loc
        if speed < 0.1 and dist < 0.05:
            self._stuck_steps += 1
        else:
            self._stuck_steps = 0
        if self._stuck_steps > 10:
            print('[Carla0915] Vehicle stuck, force done=True')
            self.done = True
        else:
            self.done = False
        obs['done'] = self.done
        time.sleep(1.0 / FPS)
        return obs

    def _get_obs(self):
        image = self.last_image if self.last_image is not None else [[0]*3]*IMAGE_SIZE[0]*IMAGE_SIZE[1]
        velocity = self.vehicle.get_velocity()
        speed = float(np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2))
        # 真实 lane_offset：车辆到最近车道中心线的横向距离
        try:
            veh_loc = self.vehicle.get_location()
            waypoint = self.world.get_map().get_waypoint(veh_loc, project_to_road=True, lane_type=carla.LaneType.Driving)
            lane_center = waypoint.transform.location
            lane_offset = veh_loc.distance(lane_center)
            right_vec = waypoint.transform.get_right_vector()
            rel_vec = veh_loc - lane_center
            sign = np.sign(right_vec.x * rel_vec.x + right_vec.y * rel_vec.y + right_vec.z * rel_vec.z)
            lane_offset *= sign
            print(f"[Carla0915] lane_offset: {lane_offset:.3f} m (veh: {veh_loc}, center: {lane_center})")
        except Exception as e:
            print(f"[Carla0915] lane_offset calc failed: {e}")
            lane_offset = 0.0
        obs = {
            'image': image,
            'speed': speed,
            'lane_offset': lane_offset,
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
