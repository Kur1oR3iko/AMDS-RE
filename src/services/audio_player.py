"""Audio playback helpers for local preset files and low-latency network streams."""

from __future__ import annotations

import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal


_MIXER_LOCK = threading.Lock()
_MIXER_READY = False


def _ensure_mixer(pygame) -> None:
    global _MIXER_READY
    if not _MIXER_READY or not pygame.mixer.get_init():
        pygame.mixer.init()
        _MIXER_READY = True


class AudioPlayer(QThread):
    """Play a local preset audio file with pygame in a worker thread."""

    started = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            import pygame

            with _MIXER_LOCK:
                _ensure_mixer(pygame)
                pygame.mixer.music.load(str(self.audio_file))
                self.started.emit()
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                    self.msleep(50)
                if self._stop_event.is_set() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
        except Exception as exc:
            print(f"音频播放错误: {exc}")
        self.finished.emit()


class NetworkStreamPlayer(QThread):
    """Play a remote MP3 stream with miniaudio to reduce network stream startup lag."""

    prepared = pyqtSignal()
    playback_started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, stream_url: str, session=None, start_paused: bool = False):
        super().__init__()
        self.stream_url = stream_url
        self.session = session
        self._stop_event = threading.Event()
        self._play_event = threading.Event()
        self._prepared_event = threading.Event()
        if not start_paused:
            self._play_event.set()
        self._source = None
        self._device = None

    def activate(self):
        """Allow a preconnected stream to start playback."""
        self._play_event.set()

    def stop(self):
        self._stop_event.set()
        self._play_event.set()
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
                def __init__(self, stream_url: str, stop_event: threading.Event, session=None):
                    self._stop_event = stop_event
                    self._buffer = bytearray()
                    self._eof = False
                    self._owns_session = session is None
                    self._session = session or requests.Session()
                    connect_started = time.perf_counter()
                    self._response = self._session.get(stream_url, stream=True, timeout=(10, 15))
                    self._response.raise_for_status()
                    print(
                        "[网络流播放器] HTTP 响应头已到达，"
                        f"等待 {time.perf_counter() - connect_started:.2f} 秒"
                    )
                    # iter_content 会尽量填满 chunk_size；16 KB 会无谓等待服务端生成更多音频。
                    self._chunks = self._response.iter_content(chunk_size=2048)
                    self._first_payload_logged = False

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
                            if not self._first_payload_logged:
                                self._first_payload_logged = True
                                print("[网络流播放器] 已收到首个音频数据块")
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
                    if self._owns_session:
                        try:
                            self._session.close()
                        except Exception:
                            pass

            stream_started = time.perf_counter()
            print("[网络流播放器] 开始连接 Vocu 流地址")
            self._source = HttpStreamSource(self.stream_url, self._stop_event, self.session)
            decoded_stream = miniaudio.stream_any(
                self._source,
                source_format=miniaudio.FileFormat.MP3,
                nchannels=2,
                sample_rate=44100,
                frames_to_read=1024,
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

            # A queued segment can connect and decode its first frame while the
            # current segment is playing.  Playback itself remains strictly
            # ordered and starts only after ChatWidget calls activate().
            self._prepared_event.set()
            self.prepared.emit()
            while not self._stop_event.is_set() and not self._play_event.wait(0.1):
                pass
            if self._stop_event.is_set():
                return

            self._device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                sample_rate=44100,
                nchannels=2,
                buffersize_msec=40,
                app_name="AMDS",
            )
            self._device.start(callback)
            print(
                "[网络流播放器] 已开始低延迟流式播放，"
                f"从连接到启动共 {time.perf_counter() - stream_started:.2f} 秒"
            )
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
