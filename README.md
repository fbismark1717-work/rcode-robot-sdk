# rcode-robot

SDK ученика для роботов **Адам** и **Ева** (RCode, Минск).

Код пишете на ноутбуке (PyCharm). Управление идёт через учебный сайт робота  
`https://<IP>:9014` (очередь слотов + безопасный proxy к API).

## Установка с GitHub

```bash
pip install "git+https://github.com/fbismark1717-work/rcode-robot-sdk.git"
```

Обновить до последней версии:

```bash
pip install -U --force-reinstall "git+https://github.com/fbismark1717-work/rcode-robot-sdk.git"
```

Для разработки (editable), если клонировали репозиторий:

```bash
git clone https://github.com/fbismark1717-work/rcode-robot-sdk.git
cd rcode-robot-sdk
pip install -e .
```

Нужен **Python 3.9+**. Внешних зависимостей нет.

## Быстрый старт

1. Робот в той же Wi‑Fi сети, открыт `https://<IP>:9014/` (самоподписанный сертификат — в браузере подтвердите исключение).
2. В PyCharm:

```python
from rcode_robot import Robot

r = Robot("192.168.31.44", slot=1, name="Аня")  # IP Адама или Евы
r.acquire()   # очередь: один ученик управляет роботом
try:
    print(r.ping())
    r.say("Привет")
    r.gesture("hello")
    r.eyes_equalizer(True)
    # аудио: r.play_audio("speech", "file.wav")
    # сервы ≤30%: r.servos_acquire(); r.servos_set({"head": 55}, speed=20); r.servos_home(); r.servos_release()
finally:
    r.release()
```

На сайте робота подробнее: `https://<IP>:9014/sdk.html`.

## Возможности

| Область | Методы |
|--------|--------|
| Очередь | `acquire`, `release`, `classroom` |
| Речь / жесты | `say`, `gesture`, `stop_speech` |
| Аудио | `audio_folders`, `audio_files`, `play_audio`, `play_phrase` |
| Глаза | `eyes_skin`, `eyes_play`, `eyes_equalizer`, `eyes_show_ip` |
| Сервы | `servos_*` (без колёс, скорость ≤ 30 %) |
| Радио | `radio_play`, `radio_stop` |

Колёса и опасные админ-API в SDK **не** входят.

## Пример из репозитория

```bash
python examples/hello_slot1.py 192.168.31.44 Аня
```

## Лицензия

Учебный пакет RCode. Использование на уроках и стендах Адам/Ева.
