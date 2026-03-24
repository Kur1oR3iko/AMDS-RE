"""
Vocu AI 音频生成模块
支持中日双语语音生成 
"""
import re
import ssl
import time
import urllib3
import requests
from pathlib import Path
from typing import Optional, Callable

# 修复SSL配置兼容性问题
ssl_context = ssl.create_default_context()
try:
    ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
except ssl.SSLError:
    # macOS 或其他系统不支持这个配置
    pass
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VocuAudioGenerator:
    """Vocu AI 音频生成器 - 异步版本"""

    API_BASE_URL = "https://v1.vocu.studio/api/tts"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        self.session.verify = False

    def generate_audio(
        self,
        text: str,
        voice_id: str,
        language: str = "ja",
        preset: str = "balance",
        speech_rate: float = 1.0,
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """生成音频（异步方式，付费用户可用，延迟似乎低很多）"""
        if callback:
            callback("创建音频生成任务...")

        result = self._create_task(text, voice_id, language, preset, speech_rate)
        if not result:
            if callback:
                callback("创建任务失败")
            return None

        if isinstance(result, dict):
            api_status = result.get("status")
            if api_status == 401:
                if callback:
                    callback("API密钥无效")
                return None
            elif api_status == 400:
                if callback:
                    callback(f"参数错误: {result.get('message')}")
                return None
            elif api_status == 403:
                if callback:
                    callback("点数不足")
                return None
            
            data = result.get("data")
            if data and isinstance(data, dict):
                audio_url = self._get_audio_url(result)
                if audio_url:
                    if callback:
                        callback("音频生成完成")
                    return audio_url
                
                task_id = data.get("id")
                task_status = data.get("status")
                
                if task_id:
                    if callback:
                        callback(f"任务创建成功: {task_id}")
                    
                    if task_status == "processing":
                        print(f"任务创建时已是processing状态，立即查询流式URL")
                        stream_result = self._check_task_status(task_id, get_stream=True)
                        if stream_result:
                            stream_url = self._get_audio_url(stream_result)
                            if stream_url and "stream.x-vocu.net" in stream_url:
                                print(f"立即获取到流式URL")
                                if callback:
                                    callback("音频流式传输中...")
                                return stream_url
                    
                    return self._poll_for_audio(task_id, callback)
                else:
                    if callback:
                        callback("无法获取任务ID")
                    return None
            else:
                if callback:
                    callback("响应格式错误")
                return None
        
        elif isinstance(result, str):
            if result == "direct_url":
                if callback:
                    callback("音频生成完成")
                return result
            
            task_id = result
            if callback:
                callback(f"任务创建成功: {task_id}")
            return self._poll_for_audio(task_id, callback)
        
        else:
            if callback:
                callback("未知的响应类型")
            return None

    def _poll_for_audio(self, task_id: str, callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """轮询等待音频生成完成"""
        max_retries = 120
        for i in range(max_retries):
            if callback:
                callback(f"生成中... ({i+1}/{max_retries})")

            result = self._check_task_status(task_id, get_stream=True)
            if result:
                api_status = result.get("status")
                
                data = result.get("data", {})
                if isinstance(data, dict):
                    task_status = data.get("status")
                else:
                    task_status = None
                
                print(f"API状态: {api_status}, 任务状态: {task_status}")

                if task_status in ["generated", "completed", "done", "success"]:
                    audio_url = self._get_audio_url(result)
                    if audio_url:
                        if callback:
                            callback("音频生成完成")
                        return audio_url
                    else:
                        print(f"状态成功但未找到URL，继续等待...")
                        time.sleep(0.1)
                        continue

                elif task_status == "processing":
                    audio_url = self._get_audio_url(result)
                    if audio_url and "stream.x-vocu.net" in audio_url:
                        print(f"获取到流式URL，立即返回")
                        if callback:
                            callback("音频流式传输中...")
                        return audio_url
                    time.sleep(0.1)
                    continue

                elif task_status in ["failed", "error"]:
                    error_msg = data.get("message", result.get("message", "未知错误"))
                    if callback:
                        callback(f"生成失败: {error_msg}")
                    return None

                time.sleep(0.1)
            else:
                if callback:
                    callback("查询状态失败，重试...")
                time.sleep(0.1)

        if callback:
            callback("生成超时")
        return None

    def _create_task(
        self,
        text: str,
        voice_id: str,
        language: str,
        preset: str,
        speech_rate: float
    ) -> Optional[dict]:
        """创建异步音频生成任务"""
        url = f"{self.API_BASE_URL}/generate"

        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        if not uuid_pattern.match(voice_id):
            print(f"警告: voice_id '{voice_id}' 不是有效的UUID格式")
            print(f"UUID格式示例: 46cc9a76-acd7-4af7-a13a-f8b1408b1848")

        payload = {
            "contents": [
                {
                    "voiceId": voice_id,
                    "text": text,
                    "language": language,
                    "preset": preset,
                    "speechRate": speech_rate,
                    "break_clone": True,
                    "flash": True,
                    "stream": True
                }
            ],
            "srt": False
        }

        try:
            print(f"发送生成请求到: {url}")
            print(f"请求体: {payload}")
            print(f"Headers: Authorization: Bearer {'*' * 10}...")

            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=120,
                verify=False
            )
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text[:2000] if len(response.text) > 2000 else response.text}")

            data = response.json()
            print(f"解析后的JSON: {data}")

            if isinstance(data, dict):
                if data.get("status") == 400:
                    print(f"API错误: {data.get('message')}")
                    print("可能的原因: voice_id格式错误、文本内容问题、或API参数错误")
                elif data.get("status") == 401:
                    print("API错误: 未授权 - 请检查API密钥是否正确")
                elif data.get("status") == 403:
                    print("API错误: 点数不足或权限不足")

            return data if isinstance(data, dict) else None

        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e}")
            print(f"响应内容: {e.response.text if hasattr(e, 'response') else '无'}")
            return None
        except requests.exceptions.Timeout:
            print("请求超时")
            return None
        except Exception as e:
            print(f"创建任务异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _check_task_status(self, task_id: str, get_stream: bool = False) -> Optional[dict]:
        """查询任务状态"""
        url = f"{self.API_BASE_URL}/generate/{task_id}"
        if get_stream:
            url += "?stream=true"
        print(f"查询任务状态: {url}")

        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=30,
                verify=False
            )
            print(f"状态查询响应码: {response.status_code}")
            print(f"状态查询响应: {response.text[:1000] if len(response.text) > 1000 else response.text}")
            
            data = response.json()

            if isinstance(data, dict):
                return data
            return None

        except Exception as e:
            print(f"查询状态异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_audio_url(self, task_data: dict) -> Optional[str]:
        """从任务数据中提取音频URL，优先返回streamUrl"""
        try:
            print(f"提取音频URL，任务数据类型: {type(task_data)}")
            print(f"任务数据键: {task_data.keys() if isinstance(task_data, dict) else 'N/A'}")
            
            data = task_data.get("data")
            if not data or not isinstance(data, dict):
                print(f"没有data字段或data不是字典")
                return None
            
            print(f"data键: {data.keys()}")
            
            stream_url = data.get("streamUrl")
            if stream_url:
                print(f"找到流式URL (data.streamUrl): {stream_url}")
                return stream_url
            
            audio_url = data.get("audio")
            if audio_url:
                print(f"找到音频URL (data.audio): {audio_url}")
                return audio_url
            
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                stream_url = metadata.get("streamUrl")
                if stream_url:
                    print(f"找到流式URL (data.metadata.streamUrl): {stream_url}")
                    return stream_url
                
                audio_url = metadata.get("audio")
                if audio_url:
                    print(f"找到音频URL (data.metadata.audio): {audio_url}")
                    return audio_url
                
                contents = metadata.get("contents", [])
                if contents and isinstance(contents, list) and len(contents) > 0:
                    first_content = contents[0]
                    if isinstance(first_content, dict):
                        stream_url = first_content.get("streamUrl")
                        if stream_url:
                            print(f"找到流式URL (data.metadata.contents[0].streamUrl): {stream_url}")
                            return stream_url
                        
                        audio_url = first_content.get("audio")
                        if audio_url:
                            print(f"找到音频URL (data.metadata.contents[0].audio): {audio_url}")
                            return audio_url

            print(f"未找到音频URL或流式URL")
            return None
        except Exception as e:
            print(f"提取音频URL异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def download_audio(self, audio_url: str, output_path: Path) -> bool:
        """下载音频文件"""
        try:
            response = self.session.get(
                audio_url,
                timeout=30
            )
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)

            return True
        except Exception as e:
            print(f"下载音频失败: {e}")
            return False

    def generate_audio_sync(
        self,
        text: str,
        voice_id: str,
        language: str = "ja",
        preset: str = "balance",
        speech_rate: float = 1.0,
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """同步实时生成音频（延迟有，而且不低）"""
        if callback:
            callback("同步生成音频...")

        url = f"{self.API_BASE_URL}/simple-generate"

        payload = {
            "voiceId": voice_id,
            "text": text,
            "language": language,
            "preset": preset,
            "break_clone": True,
            "speechRate": speech_rate,
            "flash": True,
            "stream": True
        }

        try:
            print(f"发送同步生成请求到: {url}")
            print(f"请求体: {payload}")

            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60,
                verify=False
            )
            print(f"同步响应状态码: {response.status_code}")
            print(f"同步响应内容: {response.text[:2000] if len(response.text) > 2000 else response.text}")

            data = response.json()

            if isinstance(data, dict):
                api_status = data.get("status")
                if api_status == 401:
                    if callback:
                        callback("API密钥无效")
                    return None
                elif api_status == 400:
                    if callback:
                        callback(f"参数错误: {data.get('message')}")
                    return None
                elif api_status == 403:
                    if callback:
                        callback("点数不足")
                    return None

                audio_data = data.get("data")
                if audio_data and isinstance(audio_data, dict):
                    audio_url = audio_data.get("audio")
                    if audio_url:
                        if callback:
                            callback("同步音频生成完成")
                        return audio_url
                    stream_url = audio_data.get("streamUrl")
                    if stream_url:
                        if callback:
                            callback("同步音频流式传输中...")
                        return stream_url

            if callback:
                callback("同步生成失败")
            return None

        except requests.exceptions.Timeout:
            print("同步请求超时")
            if callback:
                callback("同步生成超时")
            return None
        except Exception as e:
            print(f"同步生成异常: {e}")
            import traceback
            traceback.print_exc()
            if callback:
                callback(f"同步生成错误: {e}")
            return None
