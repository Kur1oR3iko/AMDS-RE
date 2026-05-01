"""
Vocu AI 音频生成模块
支持中日双语语音生成 - 使用异步API（免费账户支持）
"""
import requests
import time
import ssl
import urllib3
from pathlib import Path
from typing import Optional, Callable

from core.resources import get_config_dir

# 创建自定义 SSL 上下文
ssl_context = ssl.create_default_context()
ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')  # 降低安全级别
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VocuAudioGenerator:
    """Vocu AI 音频生成器 - 异步版本"""

    API_BASE_URL = "https://v1.vocu.studio/api/tts"
    SIMPLE_API_URL = "https://v1.vocu.studio/api/tts/simple-generate"

    def __init__(self, api_key: str):
        """
        初始化音频生成器

        Args:
            api_key: Vocu AI API密钥
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 创建会话并配置 SSL
        self.session = requests.Session()
        self.session.verify = False
        self.cache_dir = get_config_dir() / "vocu_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_audio(
        self,
        text: str,
        voice_id: str,
        language: str = "ja",
        preset: str = "balance",
        speech_rate: float = 1.0,
        async_mode: bool = False,
        flash_mode: bool = False,
        callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        生成音频

        Args:
            text: 要生成的文本
            voice_id: 语音角色ID
            language: 语言代码 (ja=日语, zh=中文)
            preset: 生成风格 (creative/balance/stable)
            speech_rate: 语速 (0.5-2.0)
            async_mode: 启用Vocu异步/流式生成，可能需要会员权限
            flash_mode: 启用Vocu Flash低延迟模式（可能更快，但音色稳定性可能下降）
            callback: 状态回调函数，接收状态字符串

        Returns:
            生成的音频URL，失败返回None
        """
        normalized_text = (text or "").strip()
        if not normalized_text:
            if callback:
                callback("文本为空")
            return None

        # 低延迟模式优先走文档中的同步实时接口，避免异步创建任务后再轮询带来的额外延迟。
        if async_mode:
            if callback:
                callback("尝试低延迟实时生成...")
            direct_result = self._simple_generate(
                normalized_text,
                voice_id,
                language,
                preset,
                speech_rate,
                flash=flash_mode,
                stream=True,
            )
            direct_audio = self._extract_simple_audio_url(direct_result, prefer_stream=True)
            if direct_audio:
                if callback:
                    callback("实时音频已就绪")
                return direct_audio
            print("同步实时接口未返回可用音频，回退到异步任务接口")

        # 1. 创建异步生成任务
        if callback:
            callback("创建异步音频生成任务..." if async_mode else "创建音频生成任务...")

        result = self._create_task(normalized_text, voice_id, language, preset, speech_rate, async_mode, flash_mode)
        if not result:
            if callback:
                callback("创建任务失败")
            return None

        # 检查是否直接返回了音频URL（同步响应）
        if isinstance(result, dict):
            # 检查API响应状态
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
            
            # 获取data字段
            data = result.get("data")
            if data and isinstance(data, dict):
                # 检查是否直接返回了音频（同步生成完成）
                audio_url = self._get_audio_url(result)
                if audio_url:
                    if callback:
                        callback("音频生成完成")
                    return audio_url
                
                # 需要轮询等待
                task_id = data.get("id")
                task_status = data.get("status")
                
                if task_id:
                    if callback:
                        callback(f"任务创建成功: {task_id}")
                    
                    # 异步模式下，如果创建任务时已经是processing状态，立即查询流式URL
                    if async_mode and task_status == "processing":
                        print(f"任务创建时已是processing状态，立即查询流式URL")
                        stream_result = self._check_task_status(task_id, get_stream=True)
                        if stream_result:
                            stream_url = self._get_audio_url(stream_result)
                            if stream_url and "stream.x-vocu.net" in stream_url:
                                print(f"立即获取到流式URL")
                                if callback:
                                    callback("音频流式传输中...")
                                return stream_url
                    
                    return self._poll_for_audio(task_id, async_mode, callback)
                else:
                    if callback:
                        callback("无法获取任务ID")
                    return None
            else:
                if callback:
                    callback("响应格式错误")
                return None
        
        # 返回的是任务ID字符串
        elif isinstance(result, str):
            if result == "direct_url":
                # 这个情况不应该发生，但处理一下
                if callback:
                    callback("音频生成完成")
                return result
            
            task_id = result
            if callback:
                callback(f"任务创建成功: {task_id}")
            return self._poll_for_audio(task_id, async_mode, callback)
        
        else:
            if callback:
                callback("未知的响应类型")
            return None

    def _poll_for_audio(self, task_id: str, async_mode: bool = False, callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """轮询等待音频生成完成"""
        max_retries = 120
        for i in range(max_retries):
            if callback:
                callback(f"生成中... ({i+1}/{max_retries})")

            result = self._check_task_status(task_id, get_stream=async_mode)
            if result:
                # 检查API响应状态
                api_status = result.get("status")
                
                # 获取data字段
                data = result.get("data", {})
                if isinstance(data, dict):
                    task_status = data.get("status")
                else:
                    task_status = None
                
                print(f"API状态: {api_status}, 任务状态: {task_status}")

                # 检查多种成功状态
                if task_status in ["generated", "completed", "done", "success"]:
                    audio_url = self._get_audio_url(result)
                    if audio_url:
                        if callback:
                            callback("音频生成完成")
                        return audio_url
                    else:
                        print(f"状态成功但未找到URL，继续等待...")
                        time.sleep(0.1)  # 进一步减少等待时间
                        continue

                # processing状态时，异步模式尝试获取流式URL
                elif task_status == "processing":
                    audio_url = self._get_audio_url(result)
                    if async_mode and audio_url and "stream.x-vocu.net" in audio_url:
                        print(f"获取到流式URL，立即返回")
                        if callback:
                            callback("音频流式传输中...")
                        return audio_url
                    # 如果没有流式URL，继续等待
                    time.sleep(0.1 if async_mode else 0.5)
                    continue

                elif task_status in ["failed", "error"]:
                    error_msg = data.get("message", result.get("message", "未知错误"))
                    if callback:
                        callback(f"生成失败: {error_msg}")
                    return None

                # 继续等待 (pending, generating 等)
                time.sleep(0.1 if async_mode else 0.5)
            else:
                if callback:
                    callback("查询状态失败，重试...")
                time.sleep(0.1 if async_mode else 0.5)

        if callback:
            callback("生成超时")
        return None

    def _create_task(
        self,
        text: str,
        voice_id: str,
        language: str,
        preset: str,
        speech_rate: float,
        async_mode: bool,
        flash_mode: bool = False
    ) -> Optional[dict]:
        """创建音频生成任务 - 返回完整响应数据"""
        url = f"{self.API_BASE_URL}/generate"

        # 验证 voice_id 格式（应该是UUID格式）
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
        if not uuid_pattern.match(voice_id):
            print(f"警告: voice_id '{voice_id}' 不是有效的UUID格式")
            print(f"UUID格式示例: 46cc9a76-acd7-4af7-a13a-f8b1408b1848")
            # 尝试继续发送请求，让API返回具体错误

        payload = {
            "contents": [
                {
                    "voiceId": voice_id,
                    "text": text,
                    "language": language,
                    "preset": preset,
                    "speechRate": speech_rate,
                    "break_clone": True,
                    "flash": flash_mode,
                    "stream": async_mode
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

            # 检查API错误
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

    def _simple_generate(
        self,
        text: str,
        voice_id: str,
        language: str,
        preset: str,
        speech_rate: float,
        flash: bool,
        stream: bool,
    ) -> Optional[dict]:
        """调用同步实时生成接口，优先获取可立即播放的音频地址。"""
        payload = {
            "voiceId": voice_id,
            "text": text,
            "promptId": "default",
            "preset": preset,
            "break_clone": True,
            "language": language,
            "speechRate": speech_rate,
            "flash": flash,
            "stream": stream,
            "srt": False,
        }

        try:
            print(f"发送实时生成请求到: {self.SIMPLE_API_URL}")
            print(f"实时请求体: {payload}")
            response = self.session.post(
                self.SIMPLE_API_URL,
                headers=self.headers,
                json=payload,
                timeout=120,
                verify=False,
            )
            print(f"实时生成响应码: {response.status_code}")
            body = response.text[:1200] if len(response.text) > 1200 else response.text
            print(f"实时生成响应: {body}")
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            print(f"实时生成异常: {exc}")
            import traceback
            traceback.print_exc()
            return None

    def _check_task_status(self, task_id: str, get_stream: bool = False) -> Optional[dict]:
        """查询任务状态"""
        url = f"{self.API_BASE_URL}/generate/{task_id}"
        if get_stream:
            url += "?stream=true"  # 请求流式响应地址
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

            # 返回完整的响应数据
            if isinstance(data, dict):
                return data
            return None

        except Exception as e:
            print(f"查询状态异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_audio_url(self, task_data: dict) -> Optional[str]:
        """从任务数据中提取音频URL"""
        try:
            print(f"提取音频URL，任务数据类型: {type(task_data)}")
            print(f"任务数据键: {task_data.keys() if isinstance(task_data, dict) else 'N/A'}")
            
            # API响应格式: {"status": 200, "data": {...}}
            data = task_data.get("data")
            if not data or not isinstance(data, dict):
                print(f"没有data字段或data不是字典")
                return None
            
            print(f"data键: {data.keys()}")

            # 0. 同步实时接口直返字段
            stream_url = data.get("streamUrl")
            if stream_url:
                print(f"找到流式URL (data.streamUrl): {stream_url}")
                return stream_url
            
            # 1. 检查 data.metadata.audio (合并的音频)
            metadata = data.get("metadata", {})
            if isinstance(metadata, dict):
                # 合并的音频URL
                audio_url = metadata.get("audio")
                if audio_url:
                    print(f"找到音频URL (data.metadata.audio): {audio_url}")
                    return audio_url
                
                # 单个内容的音频URL
                contents = metadata.get("contents", [])
                if contents and isinstance(contents, list) and len(contents) > 0:
                    first_content = contents[0]
                    if isinstance(first_content, dict):
                        audio_url = first_content.get("audio")
                        if audio_url:
                            print(f"找到音频URL (data.metadata.contents[0].audio): {audio_url}")
                            return audio_url
            
            # 2. 直接在data中查找audio字段
            audio_url = data.get("audio")
            if audio_url:
                print(f"找到音频URL (data.audio): {audio_url}")
                return audio_url

            print(f"未找到音频URL")
            return None
        except Exception as e:
            print(f"提取音频URL异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_simple_audio_url(self, payload: Optional[dict], prefer_stream: bool = False) -> Optional[str]:
        """从同步实时生成接口响应中提取最合适的音频地址。"""
        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        if not isinstance(data, dict):
            return None

        stream_url = data.get("streamUrl")
        audio_url = data.get("audio")

        if prefer_stream and stream_url:
            print(f"实时接口返回 streamUrl: {stream_url}")
            return stream_url
        if audio_url:
            print(f"实时接口返回 audio: {audio_url}")
            return audio_url
        if stream_url:
            print(f"实时接口返回 streamUrl: {stream_url}")
            return stream_url
        return None

    def cache_audio_to_local(self, audio_url: str, suffix: str = ".mp3") -> Optional[str]:
        """下载远程音频到本地缓存，减少远程流首播延迟。"""
        try:
            target = self.cache_dir / f"vocu_{int(time.time() * 1000)}{suffix}"
            response = self.session.get(audio_url, timeout=120, verify=False)
            response.raise_for_status()
            target.write_bytes(response.content)
            print(f"音频已缓存到本地: {target}")
            return str(target)
        except Exception as exc:
            print(f"缓存远程音频失败: {exc}")
            return None

    def download_audio(self, audio_url: str, output_path: Path) -> bool:
        """
        下载音频文件

        Args:
            audio_url: 音频URL
            output_path: 保存路径

        Returns:
            是否成功
        """
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
