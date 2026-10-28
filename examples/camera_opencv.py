#!/usr/bin/env python3
"""Снимок с камеры робота через OpenCV.

  pip install opencv-python
  pip install "git+https://github.com/fbismark1717-work/rcode-robot-sdk.git"
  python camera_opencv.py 192.168.31.44
"""
from __future__ import annotations

import sys

import cv2
from rcode_robot import Robot


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.31.44"
    out = sys.argv[2] if len(sys.argv) > 2 else "robot_shot.jpg"
    r = Robot(host, slot=1, name="camera-demo")
    url = r.camera_url()
    print("stream:", url)
    cap = cv2.VideoCapture(url)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        print("Нет кадра — проверьте hawkeye / порт 18000")
        return 1
    cv2.imwrite(out, frame)
    print("saved", out, frame.shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
