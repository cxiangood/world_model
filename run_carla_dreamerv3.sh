#!/bin/bash

# 环境配置
CARLA_ENV="python37"          # CARLA环境（Python 3.7）
DREAMER_ENV="python311"       # DreamerV3环境（Python 3.11）
CARLA_PORT=2000               # CARLA服务器端口
CARLA_SERVER_PORT=5555        # CARLA通信服务端口
CARLA_TIMEOUT=30              # CARLA启动超时时间（秒）
ZMQ_TIMEOUT=10                # ZMQ通信超时时间（秒）
ENV_CHECK_RETRIES=5           # 环境检查重试次数
ENV_CHECK_DELAY=2             # 环境检查延迟（秒）

# 路径配置
CARLA_PATH="/home/xiongxi/Carla/CARLA_0.9.13"
DREAMER_PATH="$HOME/桌面/worldmodel_dreamerv3/dreamerv3"
CARLA_GYM_PATH="$HOME/桌面/worldmodel_dreamerv3/carla_gym"
CARLA_SERVER_SCRIPT="$CARLA_GYM_PATH/carla_server.py"  # CARLA服务脚本
LOGDIR="$HOME/logdir/carla"
CARLA_PID_FILE="$CARLA_PATH/carla_pid.txt"
CARLA_SERVER_PID_FILE="$CARLA_PATH/carla_server_pid.txt"
CARLA_STATUS_FILE="$CARLA_PATH/status.txt"
DREAMER_LOG_FILE="$LOGDIR/dreamer.log"

# 函数：启动CARLA模拟器
start_carla_simulator() {
echo "🚗 启动 CARLA 模拟器 (环境: $CARLA_ENV)..."
source ~/.bashrc
rm -f "$CARLA_PID_FILE" "$CARLA_STATUS_FILE"

conda run -n "$CARLA_ENV" bash -c "
cd $CARLA_PATH
./CarlaUE4.sh -opengl -carla-port=$CARLA_PORT > carla_simulator.log 2>&1 &
sleep 5

# 匹配多种进程名
CARLA_PID=\$(pgrep -f 'CarlaUE4-Linux-Shipping' || pgrep -f 'CarlaUE4' || pgrep -f 'UE4')
if [ -n \"\$CARLA_PID\" ]; then
echo \$CARLA_PID > $CARLA_PID_FILE
echo \"1\" > $CARLA_STATUS_FILE
echo \"找到CARLA模拟器进程ID: \$CARLA_PID\"
else
echo \"0\" > $CARLA_STATUS_FILE
echo \"⚠️ 未找到CARLA模拟器进程ID，查看carla_simulator.log\"
cat carla_simulator.log
fi
"

echo "等待CARLA模拟器监听端口 $CARLA_PORT (超时: $CARLA_TIMEOUT秒)..."
for ((i=1; i<=$CARLA_TIMEOUT; i++)); do
sleep 1
PORT_STATUS=$(netstat -an | grep ":$CARLA_PORT " | grep LISTEN)
CARLA_PID=$(cat "$CARLA_PID_FILE" 2>/dev/null)

if [ -n "$CARLA_PID" ] && [ -n "$PORT_STATUS" ]; then
echo "✅ CARLA 模拟器启动完成 (PID: $CARLA_PID, 端口: $CARLA_PORT)"
break
elif [ $i -eq $CARLA_TIMEOUT ]; then
echo "⚠️ CARLA模拟器启动超时，进程ID: $CARLA_PID"
fi
done
}

# 函数：启动CARLA服务器（Python 3.7环境）
start_carla_server() {
echo "📡 启动 CARLA 通信服务器 (环境: $CARLA_ENV, 端口: $CARLA_SERVER_PORT)..."
source ~/.bashrc

if [ ! -f "$CARLA_STATUS_FILE" ] || [ $(cat "$CARLA_STATUS_FILE") -ne 1 ]; then
echo "❌ CARLA模拟器未启动，无法启动通信服务器"
return 1
fi

# 预注册环境检查
echo "🔍 预注册CARLA环境并检查路径..."
conda run -n "$CARLA_ENV" bash -c "
cd \"$CARLA_GYM_PATH\"
export PYTHONPATH=\$PYTHONPATH:$CARLA_PATH/PythonAPI/carla/dist:\$PWD

echo \"Python路径:\"
python -c \"import sys; print('\\n'.join(sys.path))\"

echo \"检查carla_gym包路径:\"
python -c \"
try:
    from carla_gym.src.env.environment import CarlaEnv
    print('✅ 成功导入CarlaEnv')
except ImportError as e:
    print('❌ 无法导入CarlaEnv:', e)
    exit(1)

import gymnasium as gym
from gymnasium.envs.registration import register
from carla_gym.src.env.environment import CarlaEnv

# 强制注册环境
print('🔧 手动注册CARLA环境...')
register(
    id=\"carla_rl-gym-v0\",
    entry_point="carla_gym.src.env.environment:CarlaEnv",
    max_episode_steps=1000,
)

# 检查环境是否已注册
env_ids = [spec for spec in gym.registry if 'carla' in spec]
if 'carla_rl-gym-v0' in env_ids:
    print('✅ CARLA环境已成功注册')
    exit(0)
else:
    print('❌ CARLA环境注册失败')
    print('已注册环境:', env_ids)
    exit(1)
\"
"

if [ $? -ne 0 ]; then
echo "❌ CARLA环境注册失败，无法启动通信服务器"
return 1
fi

# 增加延迟确保环境注册完成
echo "⏳ 等待环境注册完成..."
sleep 3

# 启动服务器
conda run -n "$CARLA_ENV" bash -c "
cd \"$CARLA_GYM_PATH\"
export PYTHONPATH=\$PYTHONPATH:$CARLA_PATH/PythonAPI/carla/dist:\$PWD

echo \"启动CARLA服务器，环境ID: carla_rl-gym-v0\"
python \"$CARLA_SERVER_SCRIPT\" --port=$CARLA_SERVER_PORT --env-id=carla_rl-gym-v0 > carla_server.log 2>&1 &

sleep 3
SERVER_PID=\$(pgrep -f \"python.*$CARLA_SERVER_SCRIPT\")
if [ -n \"\$SERVER_PID\" ]; then
echo \$SERVER_PID > $CARLA_SERVER_PID_FILE
echo \"1\" > $CARLA_STATUS_FILE
echo \"CARLA通信服务器启动成功 (PID: \$SERVER_PID, 端口: $CARLA_SERVER_PORT)\"
else
echo \"0\" > $CARLA_STATUS_FILE
echo \"⚠️ CARLA通信服务器启动失败，查看carla_server.log\"
cat carla_server.log
fi
"

echo "等待CARLA通信服务器就绪 (超时: $ZMQ_TIMEOUT秒)..."
for ((i=1; i<=$ZMQ_TIMEOUT; i++)); do
sleep 1
SERVER_PID=$(cat "$CARLA_SERVER_PID_FILE" 2>/dev/null)
PORT_STATUS=$(netstat -an | grep ":$CARLA_SERVER_PORT " | grep LISTEN)

if [ -n "$SERVER_PID" ] && [ -n "$PORT_STATUS" ]; then
echo "✅ CARLA通信服务器启动完成"
break
elif [ $i -eq $ZMQ_TIMEOUT ]; then
echo "⚠️ CARLA通信服务器启动超时，进程ID: $SERVER_PID"
fi
done
}

# 函数：启动DreamerV3（Python 3.11环境）
start_dreamerv3() {
echo "🧠 启动 DreamerV3 (环境: $DREAMER_ENV)..."
source ~/.bashrc

if [ ! -f "$CARLA_STATUS_FILE" ] || [ $(cat "$CARLA_STATUS_FILE") -ne 1 ]; then
echo "❌ CARLA服务未就绪，无法运行DreamerV3"
return 1
fi

# 增加环境存在性检查
echo "🔍 检查CARLA环境是否已注册..."
for ((i=1; i<=$ENV_CHECK_RETRIES; i++)); do
    conda run -n "$CARLA_ENV" bash -c "
    python -c \"
import gymnasium as gym
env_ids = [spec for spec in gym.registry if 'carla' in spec]
if 'carla_rl-gym-v0' in env_ids:
    print('✅ CARLA环境已注册')
    exit(0)
else:
    print('❌ CARLA环境未注册 (尝试 $i/$ENV_CHECK_RETRIES)')
    print('已注册环境:', env_ids)
    exit(1)
    \"
    "
    
    if [ $? -eq 0 ]; then
        break
    else
        if [ $i -lt $ENV_CHECK_RETRIES ]; then
            echo "⏳ 等待环境注册完成 (尝试 $i/$ENV_CHECK_RETRIES)..."
            sleep $ENV_CHECK_DELAY
        else
            echo "❌ CARLA环境注册失败，无法启动DreamerV3"
            return 1
        fi
    fi
done

# 检查服务器是否能加载环境
echo "🔍 验证CARLA服务器是否能加载环境..."
conda run -n "$CARLA_ENV" bash -c "
python -c \"
import zmq
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, $((ZMQ_TIMEOUT * 1000)))
socket.setsockopt(zmq.SNDTIMEO, $((ZMQ_TIMEOUT * 1000)))
socket.connect('tcp://localhost:${CARLA_SERVER_PORT}')

try:
    # 检查服务器是否运行
    socket.send_json({'cmd': 'ping'})
    response = socket.recv_json()
    if response.get('status') != 'success':
        print('❌ 服务器响应错误:', response)
        exit(1)
    print('✅ 服务器连接成功')
    
    # 尝试初始化环境
    print('🔧 测试环境初始化...')
    socket.send_json({'cmd': 'init'})
    response = socket.recv_json()
    if response.get('status') != 'success':
        print('❌ 环境初始化失败:', response)
        exit(1)
    print('✅ 环境初始化成功')
    
    # 清理
    socket.send_json({'cmd': 'close'})
    socket.recv_json()
    exit(0)
except Exception as e:
    print('❌ 测试失败:', str(e))
    exit(1)
\"
"

if [ $? -ne 0 ]; then
echo "❌ CARLA服务器环境测试失败，无法启动DreamerV3"
return 1
fi

# 增加延迟确保环境完全就绪
echo "⏳ 等待环境完全就绪..."
sleep 5

conda run -n "$DREAMER_ENV" bash -c "
cd \"$DREAMER_PATH\"
export PYTHONPATH=\$PYTHONPATH:\$PWD:\$CARLA_GYM_PATH
echo \"Python executable: $(which python)\" 
echo \"Python version: $(python --version)\"

if python -c \"import elements\" 2>/dev/null; then
echo \"✅ elements模块可导入\"
else
echo \"❌ 请在$DREAMER_ENV环境中安装DreamerV3依赖\"
exit 1
fi

# 检查ZMQ连接
python -c \"
import zmq, time
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.setsockopt(zmq.RCVTIMEO, $((ZMQ_TIMEOUT * 1000)))
socket.setsockopt(zmq.SNDTIMEO, $((ZMQ_TIMEOUT * 1000)))
socket.connect('tcp://localhost:${CARLA_SERVER_PORT}')
socket.send_json({'cmd': 'ping'})
try:
    response = socket.recv_json()
    print('✅ ZMQ连接测试成功')
except zmq.Again:
    print('❌ ZMQ连接失败，请检查CARLA通信服务器')
    exit(1)
\"

# 启动DreamerV3训练
python dreamerv3/main.py \
--configs carla \
--task carla_remote \
--logdir \"$LOGDIR\" \
--run.train_ratio 64 \
> \"$DREAMER_LOG_FILE\" 2>&1 &
"

echo "查看训练日志: tail -f \"$DREAMER_LOG_FILE\""
}

# 函数：停止所有进程
stop_all() {
stop_carla_server
stop_carla_simulator
}

# 函数：停止CARLA通信服务器
stop_carla_server() {
if [ -f "$CARLA_SERVER_PID_FILE" ]; then
SERVER_PID=$(cat "$CARLA_SERVER_PID_FILE")
echo "🛑 停止 CARLA 通信服务器 (PID: $SERVER_PID)..."
kill -9 $SERVER_PID 2>/dev/null
pkill -f "python.*$CARLA_SERVER_SCRIPT"
rm -f "$CARLA_SERVER_PID_FILE"
echo "✅ CARLA通信服务器已停止"
else
echo "⚠️ 未找到CARLA通信服务器进程，跳过终止"
fi
}

# 函数：停止CARLA模拟器
stop_carla_simulator() {
if [ -f "$CARLA_PID_FILE" ]; then
CARLA_PID=$(cat "$CARLA_PID_FILE")
echo "🛑 停止 CARLA 模拟器 (PID: $CARLA_PID)..."
kill -9 $CARLA_PID 2>/dev/null
pkill -f 'CarlaUE4'
rm -f "$CARLA_PID_FILE" "$CARLA_STATUS_FILE"
echo "✅ CARLA模拟器已停止"
else
echo "⚠️ 未找到CARLA模拟器进程，跳过终止"
fi
}

# 捕获终止信号
trap stop_all SIGINT SIGTERM

# 主执行流程
start_carla_simulator
start_carla_server
start_dreamerv3

# 等待用户中断
echo "按 Ctrl+C 停止所有进程..."
while true; do
sleep 1
done
