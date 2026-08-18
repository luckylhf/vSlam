import rclpy
import asyncio
import aiohttp
import os
from rclpy.node import Node
from std_msgs.msg import Int32
import json
import tempfile
import numpy as np
import sounddevice as sd  
from datetime import datetime
import struct
from socket import *
import signal
import threading
import wave
import time
from queue import Queue, Empty
from std_msgs.msg import Header

# ============================================================================
# 配置说明（通过环境变量配置，避免硬编码敏感信息）：
#   1. AUDIO_SOCKET_IP   ：语音采集 socket 服务 IP，默认 127.0.0.1
#   2. AUDIO_SOCKET_PORT ：语音采集 socket 服务端口，默认 9080
#   3. LLM_SERVER_IP     ：大模型/ASR 服务 IP，默认 127.0.0.1
#   4. LLM_SERVER_PORT   ：大模型/ASR 服务端口，默认 5006
#   5. LLM_API_TOKEN     ：大模型服务鉴权 Token（必填），从环境变量读取
#                          示例：export LLM_API_TOKEN="your_token_here"
#                          请勿将真实 Token 提交到代码仓库。
# ============================================================================

# 语音采集 socket 服务地址
AUDIO_SOCKET_IP = os.environ.get("AUDIO_SOCKET_IP", "127.0.0.1")
AUDIO_SOCKET_PORT = int(os.environ.get("AUDIO_SOCKET_PORT", "9080"))

# 大模型/ASR 服务地址
LLM_SERVER_IP = os.environ.get("LLM_SERVER_IP", "127.0.0.1")
LLM_SERVER_PORT = int(os.environ.get("LLM_SERVER_PORT", "5006"))

# 大模型服务鉴权 Token（从环境变量读取，避免硬编码泄露）
LLM_API_TOKEN = os.environ.get("LLM_API_TOKEN", "")

audio_lock = threading.Lock()

class SocketAudioProvider:
    def __init__(self):
        self.client_socket = socket(AF_INET, SOCK_STREAM)
        self.client_socket.setsockopt(SOL_SOCKET, SO_SNDBUF, 1024)
        self.server_ip_port = (AUDIO_SOCKET_IP, AUDIO_SOCKET_PORT)
        self.client_socket.connect(self.server_ip_port)
        self.client_socket.settimeout(3.0)
        self.is_first_read = True
        self.run = True

    def close(self):
        self.run = False
        self.client_socket.close()
        self.client_socket = None
        print("资源已释放")


    def connect(self):
        """创建新连接（处理异常）"""
        try:
            # 创建新socket并配置
            self.client_socket = socket(AF_INET, SOCK_STREAM)
            self.client_socket.setsockopt(SOL_SOCKET, SO_SNDBUF, 1024)
            self.server_ip_port = (AUDIO_SOCKET_IP, AUDIO_SOCKET_PORT)
            self.client_socket.connect(self.server_ip_port)
            self.client_socket.settimeout(3.0)
            self.run = True  # 连接成功后重置运行状态
            self.is_first_read = True  # 重连后视为首次读取
            print(f"成功连接到服务器 {self.server_ip_port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.client_socket = None  # 连接失败时置空
            return False


    def receive_full_data(self, expected_length):
        received_data = bytearray()
        while len(received_data) < expected_length and self.run:
            try:
                chunk = self.client_socket.recv(min(4096, expected_length - len(received_data)))
                if not chunk:
                    print("服务器关闭连接")
                    return None
                received_data.extend(chunk)
            except timeout:
                print("接收超时")
                return None
            except Exception as e:
                print(f"接收错误: {e}")
                return None
        return bytes(received_data)
    
    def read(self):
        '''        
        从socket读取音频数据，解析并返回音频数据和VAD状态。
        返回值:
            audio_data: bytes - 音频数据
            vad: int - 0: "静音", 1: "开始说话", 2: "持续说话", 3: "结束说话"
        '''
        try:


            header = self.receive_full_data(9)
            if not header:
                return None
                
            sync_head, user_id, msg_type, msg_length, msg_id = struct.unpack('<BBBIH', header)
            
            if sync_head != 0xa5 or user_id != 0x01:
                print(f"头部校验失败: sync={sync_head:02x}, user={user_id:02x}")
                return None
                
            body = self.receive_full_data(msg_length + 1)
            if not body:
                return None
                
            vad = body[0]
            channel = body[1]
            frame_id = struct.unpack('<I', body[4:8])[0]
            audio_data = body[8:-1]  # 提取音频数据
                        
            if channel == 0:
                return audio_data, vad
            return None

        except struct.error as e:
            print(f"解析错误: {e}, 数据长度: {len(body) if 'body' in locals() else 0}")
        except Exception as e:
            print(f"处理异常: {e}")


class HTTPPostNode(Node):
    def __init__(self):
        super().__init__('http_post_node')
        self.session = None
        # 大模型服务 URL，基于环境变量 LLM_SERVER_IP / LLM_SERVER_PORT 配置
        self.url = f"http://{LLM_SERVER_IP}:{LLM_SERVER_PORT}/chatSTX/v2/chat"
        self.url_first = f"http://{LLM_SERVER_IP}:{LLM_SERVER_PORT}/speech/v1/asr"
        self.sample_rate = 16000
        self.channels = 1
        self.bit_depth = 16
        self.int32_publisher = self.create_publisher(
            Int32, 
            "/action_command",  # 自定义话题名，可根据需求修改
            10  # 队列大小，按需调整
        )
        self.recording = None
        self.recording_active = True
        self.audio_buffer = bytearray()
        self.frames = []
        self.audio_provider = SocketAudioProvider()

    def publish_int32_data(self, data: int):
        """发布 int32 类型数据到指定话题"""
        msg = Int32()
        msg.data = data  # 赋值 int32 数据
        self.int32_publisher.publish(msg)
        self.get_logger().info(f"发布 int32 数据: {data} 到话题 /custom_int32_topic")
        
    async def init_session(self):
        # 启用连接池和超时控制
        connector = aiohttp.TCPConnector(ssl=False, limit_per_host=5)
        self.session = aiohttp.ClientSession(connector=connector)

    async def download_audio(self, url):
        """下载网络音频到临时文件"""
        temp_file = Path(tempfile.gettempdir()) / "temp_audio.wav"
        async with self.session.get(url) as response:
            if response.status != 200:
                raise ConnectionError(f"下载失败: HTTP {response.status}")
            
            with open(temp_file, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk: break
                    f.write(chunk)
        return temp_file

    async def send_post_request_first(self, max_retry: int = 3):
        if not self.session:
            await self.init_session()

        # 鉴权 Token 从环境变量 LLM_API_TOKEN 读取，避免硬编码泄露
        headers = {"Authorization": f"Bearer {LLM_API_TOKEN}"}
        file_path = Path.cwd() / "install" / "audio_http_pkg" / "output.wav"

        for attempt in range(1, max_retry + 1):
            # 每次重试都重新构造 FormData 并重新打开文件
            form_data = aiohttp.FormData()
            form_data.add_field('project_id', '3')
            form_data.add_field('role', '0')
            form_data.add_field('response_length', '100')
            form_data.add_field('audio_format', 'wav')

            # 用 async with aiofiles.open 也可以，这里用普通 open 也可以
            try:
                file = open(file_path, 'rb')
                form_data.add_field(
                    'audio',
                    file,
                    filename='audio.wav',
                    content_type='audio/wav'
                )

                async with self.session.post(
                    self.url_first,
                    headers=headers,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_data = await response.json()

                    if not response_data.get('data', {}).get('audioPath'):
                        self.get_logger().error("响应缺少audioPath字段")
                    else:
                        return response_data      # 成功拿到结果，直接返回

            except aiohttp.ClientConnectorError as e:
                self.get_logger().error(f"连接失败: {e}")
            except asyncio.TimeoutError:
                self.get_logger().error("请求超时")
            except aiohttp.ContentTypeError as e:
                # 服务器返回的不是 JSON
                self.get_logger().error(f"内容类型错误: {e}")
            except Exception as e:
                self.get_logger().error(f"请求异常: {e}")
            finally:
                # 确保文件句柄关闭
                try:
                    file.close()
                except Exception:
                    pass

            if attempt < max_retry:
                self.get_logger().info(f"第 {attempt} 次请求失败，1 秒后重试...")
                await asyncio.sleep(1)     # 非阻塞
            else:
                self.get_logger().error("已达到最大重试次数，放弃请求")
                return None

        
        
    async def send_post_request(self, max_retry: int = 5):
        if not self.session:
            await self.init_session()

        # 鉴权 Token 从环境变量 LLM_API_TOKEN 读取，避免硬编码泄露
        headers = {"Authorization": f"Bearer {LLM_API_TOKEN}"}
        file_path = Path.cwd() / "install" / "audio_http_pkg" / "output.wav"

        for attempt in range(1, max_retry + 1):
            # 每次重试都重新构造 FormData 并重新打开文件
            form_data = aiohttp.FormData()
            form_data.add_field('project_id', '3')
            form_data.add_field('role', '0')
            form_data.add_field('response_length', '100')
            form_data.add_field('audio_format', 'wav')

            # 用 async with aiofiles.open 也可以，这里用普通 open 也可以
            try:
                file = open(file_path, 'rb')
                form_data.add_field(
                    'audio',
                    file,
                    filename='audio.wav',
                    content_type='audio/wav'
                )

                async with self.session.post(
                    self.url,
                    headers=headers,
                    data=form_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_data = await response.json()

                    if not response_data.get('data', {}).get('audioPath'):
                        self.get_logger().error("响应缺少audioPath字段")
                    else:
                        return response_data      # 成功拿到结果，直接返回

            except aiohttp.ClientConnectorError as e:
                self.get_logger().error(f"连接失败: {e}")
            except asyncio.TimeoutError:
                self.get_logger().error("请求超时")
            except aiohttp.ContentTypeError as e:
                # 服务器返回的不是 JSON
                self.get_logger().error(f"内容类型错误: {e}")
            except Exception as e:
                self.get_logger().error(f"请求异常: {e}")
            finally:
                # 确保文件句柄关闭
                try:
                    file.close()
                except Exception:
                    pass

            if attempt < max_retry:
                self.get_logger().info(f"第 {attempt} 次请求失败，1 秒后重试...")
                await asyncio.sleep(1)     # 非阻塞
            else:
                self.get_logger().error("已达到最大重试次数，放弃请求")
                return None

    async def record_on_speech(self):
        """说话时开始录音，静音持续2秒后自动停止"""
        self.audio_provider.close()
        time.sleep(1)
        self.audio_provider.connect()
        self.get_logger().info("等待语音...")
        self.frames = []
        self.audio_provider.is_first_read  = True
        silence_counter = 0

        while rclpy.ok(): 
            audio_res = self.audio_provider.read()
            if audio_res is None:
                continue

            audio_data, vad = audio_res
            if vad == 1:
                self.get_logger().info("开始说话，先清空缓存，然后缓存音频数据")
                self.audio_buffer.clear()
                self.audio_buffer.extend(audio_data)
                silence_counter = 0
            elif vad == 2:
                self.get_logger().info("持续说话，继续缓存音频数据")
                self.audio_buffer.extend(audio_data)
                silence_counter = 0
            elif vad == 3:
                self.get_logger().info("结束说话，保存音频数据")
                if not self.recording_active:
                    self.recording_active = True
                    continue
                self.audio_buffer.extend(audio_data)
                sentence_audio_data = bytes(self.audio_buffer)
                silence_counter = 0
                file_path = Path.cwd() / "install" / "audio_http_pkg" / "output.wav"
                file_path.parent.mkdir(parents=True, exist_ok=True)

                if not sentence_audio_data:
                    self.get_logger().info("没有音频数据可保存")
                    break

                try:
                    with wave.open(str(file_path), 'wb') as wf:
                        wf.setnchannels(self.channels)
                        wf.setsampwidth(self.bit_depth // 8)
                        wf.setframerate(self.sample_rate)
                        wf.writeframes(sentence_audio_data)
                    self.get_logger().info(f"已转换为WAV格式: {file_path}")
                except Exception as e:
                    self.get_logger().info(f"保存WAV文件失败: {e}")
                break
            #elif vad == 0:
                #silence_counter += 1
                #if silence_counter >= 120:
                #    self.get_logger().info("唤醒中止1")
                #    return "中止"

    async def play_audio(self, file_path):
        #file_path = str(file_path)
        self.get_logger().info(f"播放音频: {file_path}")
        #self.recording_active = False
        try:
            import wave
            with wave.open(str(file_path), 'rb') as wf:
                n_channels = wf.getnchannels()
                samp_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                raw_data = wf.readframes(wf.getnframes())

            
            # 转换字节为NumPy数组
            dtype_map = {1: np.uint8, 2: np.int16, 4: np.int32}
            if samp_width not in dtype_map:
                raise ValueError(f"不支持的采样宽度: {samp_width}字节")
                
            audio_array = np.frombuffer(raw_data, dtype=dtype_map[samp_width])
            
            # 处理多通道数据
            if n_channels > 1:
                audio_array = audio_array.reshape(-1, n_channels)
            
            # 播放音频
            #sd.play(audio_array, samplerate=frame_rate, blocksize=4096, latency=0.1)
            #sd.wait()
            #sd.stop()
            with audio_lock:
                sd.play(audio_array, samplerate=frame_rate, blocksize=4096, latency=0.1)
                sd.wait()
                sd.stop()
                
        except Exception as e:
            self.get_logger().error(f"播放失败: {str(e)}")
            raise
    
async def main_async(args=None):
    rclpy.init(args=args)
    node = HTTPPostNode()
    try:
        await node.init_session()                
        while rclpy.ok(): 
            await node.record_on_speech()
            # 1. 发送请求获取响应字典
            response_dict = await node.send_post_request_first()
            if not response_dict:
                continue  # 如果请求失败，继续下一次循环

            # 2. 直接访问字典字段
            query_data = response_dict.get('data', {}).get('text')
            target = "小讲解员"
            target1 = "握"
            target2 = "手"
            target3 = "鞠"
            target4 = "躬"
            target5 = "打"
            target6 = "招呼"
            target7 = "跳"
            target8 = "舞"
            print(f"字符串aa'{query_data}'")
            matched = False
            if query_data and target in query_data: 
                if query_data and target1 in query_data:
                    if query_data and target2 in query_data:
                        node.publish_int32_data(1)
                        matched = True
                if query_data and target3 in query_data:
                    if query_data and target4 in query_data:
                        node.publish_int32_data(3)
                        matched = True
                if query_data and target5 in query_data:
                    if query_data and target6 in query_data:
                        node.publish_int32_data(2)
                        matched = True
                if query_data and target7 in query_data:
                    if query_data and target8 in query_data:
                        node.publish_int32_data(4)
                        matched = True
            
            if not matched and query_data and target in query_data: 
                print(f"字符串11111 '{query_data}'")
                
                # 1. 发送请求获取响应字典
                def play_audio_threaded(node):
                    """线程化播放音频 - 不会阻塞主线程"""
                    def audio_task():
                        #print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始线程播放音频: {audio_file}")
                        frame_rate = 16000
                        duration = 0.2
                        samples = np.arange(int(frame_rate * duration))
                        audio_array = (
                            0.1 * np.sin(2 * np.pi * 440 * samples / frame_rate)
                        ).astype(np.float32)

                        with audio_lock:
                            sd.play(audio_array, samplerate=frame_rate, blocksize=4096, latency=0.1)
                            sd.wait()
                            sd.stop()

                    # 创建并启动线程
                    thread = threading.Thread(target=audio_task, daemon=True)
                    thread.start()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 音频播放线程已启动，主线程继续执行")

                print(f"字符串444 '{query_data}'")   
                play_audio_threaded(node)
                response_dict = await node.send_post_request()
                if not response_dict:
                    continue  # 如果请求失败，继续下一次循环

                # 2. 直接访问字典字段
                audio_url = response_dict.get('data', {}).get('audioPath')
                if not audio_url:
                    node.get_logger().error("响应缺少audioPath字段")
                    continue

                node.get_logger().info(f"获取音频URL: {audio_url}")
                # 3. 下载网络音频
                try:
                    local_file = await node.download_audio(audio_url)
                    node.get_logger().info(f"音频已下载到: {local_file}")
                    # 4. 播放本地音频
                    await node.play_audio(local_file)
                except Exception as e:
                    node.get_logger().error(f"处理音频失败: {str(e)}")
        
    except Exception as e:
        node.get_logger().error(f"节点异常: {str(e)}")
    finally:
        if node.session:
            await node.session.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

def main(args=None):
    asyncio.run(main_async(args))

if __name__ == '__main__':
    main()
