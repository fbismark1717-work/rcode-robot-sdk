"""Robot client — HTTPS :9014 session + whitelist proxy."""
from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any


class RobotError(RuntimeError):
    pass


MANUAL_SPEED_MAX = 30


class Robot:
    """Ученик → очередь на роботе → действия через proxy."""

    def __init__(
        self,
        host: str,
        slot: int = 1,
        name: str = "",
        port: int = 9014,
        verify: bool = False,
        lease_heartbeat_s: float = 10.0,
    ) -> None:
        self.host = host.strip()
        self.slot = int(slot)
        self.name = name or f"Слот {self.slot}"
        self.port = int(port)
        self.verify = verify
        self.lease_heartbeat_s = lease_heartbeat_s
        self.token: str | None = None
        self._manual_client: str | None = None
        self._hb_stop = threading.Event()
        self._hb_thread: threading.Thread | None = None
        self._ctx = ssl.create_default_context()
        if not verify:
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE

    @property
    def base(self) -> str:
        return f"https://{self.host}:{self.port}"

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        auth: bool = False,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method.upper()
        )
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = {"error": raw}
            raise RobotError(payload.get("error") or f"HTTP {err.code}") from err
        except Exception as err:
            raise RobotError(str(err)) from err

    def classroom(self) -> dict[str, Any]:
        return self._request("GET", "/api/classroom")

    def acquire(self, wait: bool = True, poll_s: float = 1.0, timeout_s: float = 300.0) -> dict[str, Any]:
        out = self._request(
            "POST",
            "/api/session/acquire",
            {"slot": self.slot, "name": self.name},
        )
        if not out.get("success"):
            raise RobotError(out.get("error") or "acquire failed")
        self.token = out.get("token")
        self._manual_client = f"sdk-s{self.slot}-{(self.token or '')[-8:]}"
        self._start_heartbeat()
        if out.get("status") == "running" or not wait:
            return out
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(poll_s)
            hb = self.heartbeat()
            if hb.get("status") == "running":
                return hb
        raise RobotError("Таймаут ожидания очереди")

    def heartbeat(self) -> dict[str, Any]:
        if not self.token:
            raise RobotError("Нет token — сначала acquire()")
        return self._request(
            "POST", "/api/session/heartbeat", {"token": self.token}, auth=True
        )

    def release(self) -> dict[str, Any]:
        self._stop_heartbeat()
        try:
            if self._manual_client:
                try:
                    self.servos_release()
                except Exception:
                    pass
        finally:
            self._manual_client = None
        if not self.token:
            return {"success": True, "released": False}
        try:
            return self._request(
                "POST", "/api/session/release", {"token": self.token}, auth=True
            )
        finally:
            self.token = None

    def _start_heartbeat(self) -> None:
        self._stop_heartbeat()
        self._hb_stop.clear()

        def loop() -> None:
            while not self._hb_stop.wait(self.lease_heartbeat_s):
                try:
                    self.heartbeat()
                except Exception:
                    pass

        self._hb_thread = threading.Thread(target=loop, name="rcode-hb", daemon=True)
        self._hb_thread.start()

    def _stop_heartbeat(self) -> None:
        self._hb_stop.set()
        self._hb_thread = None

    def proxy(
        self,
        path: str,
        method: str = "GET",
        body: Any = None,
        query: dict | str | None = None,
    ) -> dict[str, Any]:
        if not self.token:
            raise RobotError("Нет token — сначала acquire()")
        payload: dict[str, Any] = {"method": method, "path": path}
        if body is not None:
            payload["body"] = body
        if query is not None:
            payload["query"] = query
        return self._request("POST", "/api/proxy", payload, auth=True)

    def ping(self) -> dict[str, Any]:
        return self.proxy("/api/ping")

    # ---- речь / жесты ----

    def say(self, text: str, profile: str = "Eva") -> dict[str, Any]:
        syn = self.proxy(
            "/api/tts/synthesize",
            method="GET",
            query={"text": text, "profile": profile, "folder": "speech"},
        )
        files = syn.get("files") or []
        if files:
            fn = files[0].get("filename") or files[0].get("file")
            if fn:
                return self.proxy(
                    "/api/tts/play_robot",
                    method="GET",
                    query={"folder": "speech", "filename": fn},
                )
        return syn

    def gesture(self, preset: str) -> dict[str, Any]:
        return self.proxy(
            "/api/tts/play_anim", method="GET", query={"preset": preset}
        )

    def gestures(self) -> dict[str, Any]:
        return self.proxy("/api/tts/gestures")

    def stop_speech(self) -> dict[str, Any]:
        return self.proxy("/api/tts/stop_robot", method="POST", body={})

    # ---- аудиофайлы ----

    def audio_folders(self) -> dict[str, Any]:
        """Список папок библиотеки WAV на роботе."""
        return self.proxy("/api/tts/folders")

    def audio_files(self, folder: str = "speech") -> dict[str, Any]:
        """Список файлов в папке (например speech, Local_audio/…)."""
        return self.proxy("/api/tts/files", method="GET", query={"folder": folder})

    def play_audio(self, folder: str, filename: str) -> dict[str, Any]:
        """Проиграть WAV на колонках (+ жест, если есть в ролике)."""
        return self.proxy(
            "/api/tts/play_robot",
            method="GET",
            query={"folder": folder, "filename": filename},
        )

    def play_audio_all(self, folder: str) -> dict[str, Any]:
        return self.proxy(
            "/api/tts/play_robot_all",
            method="GET",
            query={"folder": folder},
        )

    def play_phrase(
        self,
        file: str,
        root: str = "root",
        path: str = "",
        motion: bool = True,
    ) -> dict[str, Any]:
        """Фраза из библиотеки «Фразы»."""
        return self.proxy(
            "/api/tts/phrases/play",
            method="POST",
            body={"root": root, "path": path, "file": file, "motion": motion},
        )

    def phrases_tree(self) -> dict[str, Any]:
        return self.proxy("/api/tts/phrases/tree")

    # ---- радио / громкость ----

    def radio_play(self, station: str = "3") -> dict[str, Any]:
        return self.proxy(
            "/api/media/radio/play", method="POST", body={"station": str(station)}
        )

    def radio_stop(self) -> dict[str, Any]:
        return self.proxy(
            "/api/media/radio/stop", method="POST", body={"reason": "sdk"}
        )

    def volume(self, level: int) -> dict[str, Any]:
        return self.proxy(
            "/api/volume/set", method="POST", body={"volume": int(level)}
        )

    # ---- глаза ----

    def eyes_status(self) -> dict[str, Any]:
        return self.proxy("/api/eyes/status")

    def eyes_skins(self) -> dict[str, Any]:
        return self.proxy("/api/eyes/skins")

    def eyes_equalizer(self, on: bool = True) -> dict[str, Any]:
        return self.proxy(
            "/api/eyes/equalizer", method="POST", body={"on": bool(on), "source": "sdk"}
        )

    def eyes_play(
        self,
        left: str,
        right: str | None = None,
        mode: str = "once",
        loops: int = 1,
        hold_s: float = 0,
    ) -> dict[str, Any]:
        """Показать GIF на глазах (пути к файлам на роботе)."""
        return self.proxy(
            "/api/eyes/play",
            method="POST",
            body={
                "left": left,
                "right": right or left,
                "mode": mode,
                "loops": int(loops),
                "hold_s": float(hold_s),
                "source": "sdk",
            },
        )

    def eyes_skin(self, group: str, file: str, persist: bool = False) -> dict[str, Any]:
        """Скин из каталога (group + file.gif)."""
        return self.proxy(
            "/api/eyes/skin",
            method="POST",
            body={
                "group": group,
                "file": file,
                "persist": bool(persist),
                "source": "sdk",
            },
        )

    def eyes_preview(self, group: str, file: str, loops: int = 2) -> dict[str, Any]:
        return self.proxy(
            "/api/eyes/preview",
            method="POST",
            body={"group": group, "file": file, "loops": int(loops), "source": "sdk"},
        )

    def eyes_show_ip(self, hold_s: float = 20) -> dict[str, Any]:
        return self.proxy(
            "/api/eyes/show_ip",
            method="POST",
            body={"hold_s": float(hold_s), "source": "sdk"},
        )

    # ---- сервоприводы (manual, без колёс, скорость ≤ 30 %) ----

    def _mc(self) -> str:
        if not self._manual_client:
            self._manual_client = f"sdk-s{self.slot}-{(self.token or 'x')[-8:]}"
        return self._manual_client

    def servos_state(self) -> dict[str, Any]:
        return self.proxy(
            "/api/manual/state", method="POST", body={"client": self._mc()}
        )

    def servos_acquire(self, takeover: bool = False) -> dict[str, Any]:
        """Взять ручное управление верхней частью (не колёса)."""
        return self.proxy(
            "/api/manual/acquire",
            method="POST",
            body={"client": self._mc(), "takeover": bool(takeover)},
        )

    def servos_set(
        self,
        targets: dict[str, float],
        speed: int = 20,
    ) -> dict[str, Any]:
        """Цели суставов в % (например {"head": 55}). Скорость ограничена ≤ 30 %."""
        spd = max(1, min(MANUAL_SPEED_MAX, int(speed)))
        return self.proxy(
            "/api/manual/heartbeat",
            method="POST",
            body={"client": self._mc(), "targets": targets, "speed": spd},
        )

    def servos_home(self) -> dict[str, Any]:
        return self.proxy(
            "/api/manual/home", method="POST", body={"client": self._mc()}
        )

    def servos_stop(self) -> dict[str, Any]:
        return self.proxy(
            "/api/manual/stop", method="POST", body={"client": self._mc()}
        )

    def servos_release(self) -> dict[str, Any]:
        return self.proxy(
            "/api/manual/release", method="POST", body={"client": self._mc()}
        )

    def servos_motions(self) -> dict[str, Any]:
        return self.proxy("/api/manual/motions", method="GET")

    def __enter__(self) -> "Robot":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
