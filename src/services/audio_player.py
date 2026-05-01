"""Audio playback helpers for local preset files and low-latency network streams."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal


class AudioPlayer(QThread):
    """Play a local preset audio file with pygame in a worker thread."""

    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file

    def run(self):
        try:
            import pygame

            pygame.mixer.init()
            pygame.mixer.music.load(str(self.audio_file))
            self.started.emit()
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                self.msleep(100)
        except Exception as exc:
            print(f"音频播放错误: {exc}")
        self.finished.emit()


class NetworkStreamPlayer(QThread):
    """Play a remote MP3 stream with miniaudio to reduce network stream startup lag."""

    playback_started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, stream_url: str):
        super().__init__()
        self.stream_url = stream_url
        self._stop_event = threading.Event()
        self._source = None
        self._device = None

    def stop(self):
        self._stop_event.set()
        if self._device is not None:
            try:
                self._device.stop()
            except Exception:
                pass
        if self._source is not None:
            self._source.close()

    def run(self):
        finished_event = threading.Event()

        try:
            import miniaudio
            import requests

            class HttpStreamSource(miniaudio.StreamableSource):
                def __init__(self, stream_url: str, stop_event: threading.Event):
                    self._stop_event = stop_event
                    self._buffer = bytearray()
                    self._eof = False
                    self._session = requests.Session()
                    self._session.verify = False
                    self._response = self._session.get(stream_url, stream=True, timeout=(10, 10), verify=False)
                    self._response.raise_for_status()
                    self._chunks = self._response.iter_content(chunk_size=16384)

                def read(self, num_bytes: int):
                    if self._stop_event.is_set():
                        return b""

                    while len(self._buffer) < num_bytes and not self._eof and not self._stop_event.is_set():
                        try:
                            chunk = next(self._chunks)
                        except StopIteration:
                            self._eof = True
                            break

                        if chunk:
                            self._buffer.extend(chunk)

                    if not self._buffer and self._eof:
                        return b""

                    size = min(num_bytes, len(self._buffer))
                    data = bytes(self._buffer[:size])
                    del self._buffer[:size]
                    return data

                def close(self):
                    try:
                        self._response.close()
                    except Exception:
                        pass
                    try:
                        self._session.close()
                    except Exception:
                        pass

            print(f"[网络流播放器] 开始连接流地址: {self.stream_url}")
            self._source = HttpStreamSource(self.stream_url, self._stop_event)
            decoded_stream = miniaudio.stream_any(
                self._source,
                source_format=miniaudio.FileFormat.MP3,
                nchannels=2,
                sample_rate=44100,
                frames_to_read=2048,
            )

            try:
                first_chunk = next(decoded_stream)
            except StopIteration as exc:
                raise RuntimeError("音频流没有返回可播放数据") from exc

            def playback_callback():
                frames_requested = yield first_chunk
                try:
                    while not self._stop_event.is_set():
                        try:
                            chunk = decoded_stream.send(frames_requested)
                        except StopIteration:
                            break
                        frames_requested = yield chunk
                finally:
                    finished_event.set()

            callback = playback_callback()
            next(callback)

            self._device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                sample_rate=44100,
                nchannels=2,
                buffersize_msec=60,
                app_name="AMDS",
            )
            self._device.start(callback)
            print("[网络流播放器] 已开始低延迟流式播放")
            self.playback_started.emit()

            while not self._stop_event.is_set() and not finished_event.wait(0.1):
                pass

        except Exception as exc:
            print(f"[网络流播放器] 播放失败: {exc}")
            self.error.emit(str(exc))
        finally:
            if self._device is not None:
                try:
                    self._device.stop()
                except Exception:
                    pass
                self._device = None
            if self._source is not None:
                self._source.close()
                self._source = None
            self.finished.emit()
