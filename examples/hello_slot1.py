#!/usr/bin/env python3
"""Пример слота 1: очередь + приветствие.

  pip install -e ../
  python hello_slot1.py 192.168.31.44
"""
from __future__ import annotations

import sys

from rcode_robot import Robot


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.31.44"
    name = sys.argv[2] if len(sys.argv) > 2 else "Ученик1"
    r = Robot(host, slot=1, name=name)
    print("classroom:", r.classroom())
    print("acquire…")
    r.acquire()
    try:
        print("ping:", r.ping())
        print("say…")
        print(r.say("Привет, я слот один"))
    finally:
        print("release:", r.release())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
