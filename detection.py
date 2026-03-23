"""
Requirements:
pip install opencv-python mediapipe numpy
"""

import argparse
import time
import collections
import math
import sys

import cv2
import mediapipe as mp
import numpy as np


class Config:
    DETECTION_CONFIDENCE = 0.5
    TRACKING_CONFIDENCE  = 0.5

    HISTORY_FRAMES = 20

    TORSO_ANGLE_THRESHOLD = 60

    BBOX_ASPECT_RATIO_THRESHOLD = 1.2

    VELOCITY_THRESHOLD = 0.04


    CONSECUTIVE_FRAMES = 3

    ALERT_COOLDOWN_SECONDS = 5

    ALERT_DISPLAY_SECONDS = 3


class LM:
    NOSE           = 0
    LEFT_SHOULDER  = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP       = 23
    RIGHT_HIP      = 24
    LEFT_ANKLE     = 27
    RIGHT_ANKLE    = 28

def get_landmark(landmarks, idx, frame_w, frame_h):
    lm = landmarks[idx]
    return (int(lm.x * frame_w), int(lm.y * frame_h)), lm.visibility


def midpoint(p1, p2):
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def angle_from_vertical(top, bottom):
    dx = bottom[0] - top[0]
    dy = bottom[1] - top[1]
    angle = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))
    return angle


def bbox_of_landmarks(landmarks, frame_w, frame_h, indices):
    xs = [landmarks[i].x * frame_w for i in indices]
    ys = [landmarks[i].y * frame_h for i in indices]
    return min(xs), min(ys), max(xs), max(ys)



class FallDetector:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        self.history = collections.deque(maxlen=cfg.HISTORY_FRAMES)

        self.consecutive_fall_frames = 0
        self.fall_active             = False      
        self.last_alert_time         = 0.0
        self.alert_until             = 0.0    


    def _analyse(self, landmarks, frame_w, frame_h):
        def nxy(idx):
            lm = landmarks[idx]
            return lm.x, lm.y

        ls = nxy(LM.LEFT_SHOULDER)
        rs = nxy(LM.RIGHT_SHOULDER)
        lh = nxy(LM.LEFT_HIP)
        rh = nxy(LM.RIGHT_HIP)

        shoulder_mid = ((ls[0]+rs[0])/2, (ls[1]+rs[1])/2)
        hip_mid      = ((lh[0]+rh[0])/2, (lh[1]+rh[1])/2)

        torso_angle = angle_from_vertical(shoulder_mid, hip_mid)

        body_indices = [
            LM.LEFT_SHOULDER, LM.RIGHT_SHOULDER,
            LM.LEFT_HIP,      LM.RIGHT_HIP,
            LM.LEFT_ANKLE,    LM.RIGHT_ANKLE,
        ]
        x1, y1, x2, y2 = bbox_of_landmarks(landmarks, frame_w, frame_h, body_indices)
        bbox_w = max(x2 - x1, 1)
        bbox_h = max(y2 - y1, 1)
        aspect_ratio = bbox_w / bbox_h  

        com_y = (shoulder_mid[1] + hip_mid[1]) / 2

        return {
            "torso_angle":  torso_angle,
            "aspect_ratio": aspect_ratio,
            "com_y":        com_y,         
            "shoulder_mid": shoulder_mid,
            "hip_mid":      hip_mid,
        }

    def _velocity(self):
       
        if len(self.history) < 2:
            return 0.0
        return self.history[-1]["com_y"] - self.history[-2]["com_y"]


    def update(self, landmarks, frame_w, frame_h):
 
        metrics = self._analyse(landmarks, frame_w, frame_h)
        self.history.append(metrics)
        velocity = self._velocity()

        cfg = self.cfg
        now = time.time()

        is_horizontal   = metrics["torso_angle"]  > cfg.TORSO_ANGLE_THRESHOLD
        is_wide_bbox    = metrics["aspect_ratio"] > cfg.BBOX_ASPECT_RATIO_THRESHOLD
        is_fast_drop    = velocity                 > cfg.VELOCITY_THRESHOLD

        fall_signal = is_horizontal or (is_wide_bbox and is_fast_drop)

        if fall_signal:
            self.consecutive_fall_frames += 1
        else:
            self.consecutive_fall_frames = max(0, self.consecutive_fall_frames - 1)

        newly_detected = False
        if (self.consecutive_fall_frames >= cfg.CONSECUTIVE_FRAMES
                and not self.fall_active
                and (now - self.last_alert_time) > cfg.ALERT_COOLDOWN_SECONDS):
            self.fall_active   = True
            self.last_alert_time = now
            self.alert_until   = now + cfg.ALERT_DISPLAY_SECONDS
            newly_detected     = True

        if not fall_signal and self.fall_active and now > self.alert_until:
            self.fall_active = False

        return newly_detected, metrics, {
            "is_horizontal":  is_horizontal,
            "is_wide_bbox":   is_wide_bbox,
            "is_fast_drop":   is_fast_drop,
            "velocity":       velocity,
            "consecutive":    self.consecutive_fall_frames,
        }

    def reset(self):
        self.consecutive_fall_frames = 0
        self.fall_active = False


class HUD:
    FONT       = cv2.FONT_HERSHEY_SIMPLEX
    GREEN      = (0, 220, 0)
    RED        = (0, 0, 220)
    YELLOW     = (0, 200, 220)
    WHITE      = (255, 255, 255)
    BLACK      = (0, 0, 0)
    DARK_PANEL = (20, 20, 20)

    @staticmethod
    def draw_fall_banner(frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h//3), (w, 2*h//3), (0, 0, 180), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        text  = "⚠  FALL DETECTED  ⚠"
        scale = 1.8
        thick = 3
        (tw, th), _ = cv2.getTextSize(text, HUD.FONT, scale, thick)
        cx = (w - tw) // 2
        cy = (h + th) // 2
        cv2.putText(frame, text, (cx+3, cy+3), HUD.FONT, scale, HUD.BLACK, thick+2)
        cv2.putText(frame, text, (cx, cy),     HUD.FONT, scale, HUD.WHITE, thick)

    @staticmethod
    def draw_status_panel(frame, metrics, signals, show_skeleton, fall_active):
        lines = [
            f"Torso angle : {metrics['torso_angle']:5.1f} deg",
            f"Bbox ratio  : {metrics['aspect_ratio']:5.2f}",
            f"Drop vel    : {signals['velocity']:+.4f}",
            f"Consec fall : {signals['consecutive']}",
            "",
            f"Horizontal  : {'YES' if signals['is_horizontal'] else 'no'}",
            f"Wide bbox   : {'YES' if signals['is_wide_bbox'] else 'no'}",
            f"Fast drop   : {'YES' if signals['is_fast_drop'] else 'no'}",
            "",
            f"Skeleton    : {'ON' if show_skeleton else 'OFF'}",
            f"Fall active : {'YES' if fall_active else 'no'}",
        ]
        panel_w, line_h, pad = 270, 18, 8
        panel_h = len(lines) * line_h + pad * 2

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), HUD.DARK_PANEL, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        for i, line in enumerate(lines):
            y = pad + (i + 1) * line_h
            colour = HUD.WHITE
            if "YES" in line:
                colour = HUD.YELLOW if not fall_active else HUD.RED
            cv2.putText(frame, line, (pad, y), HUD.FONT, 0.45, colour, 1)

    @staticmethod
    def draw_controls(frame):
        h = frame.shape[0]
        tips = ["Q: quit", "R: reset", "S: skeleton"]
        for i, t in enumerate(tips):
            cv2.putText(frame, t, (10, h - 10 - i * 18),
                        HUD.FONT, 0.4, (180, 180, 180), 1)

def run(source):
    cfg      = Config()
    detector = FallDetector(cfg)
    mp_pose  = mp.solutions.pose
    mp_draw  = mp.solutions.drawing_utils
    mp_styles= mp.solutions.drawing_styles

    try:
        source = int(source)
    except (ValueError, TypeError):
        pass

    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {source}")
        sys.exit(1)

    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 30
    print(f"[INFO] Stream opened  {frame_w}x{frame_h}  @{fps_src:.1f} fps")

    show_skeleton = True
    prev_time     = time.time()

    with mp_pose.Pose(
        min_detection_confidence=cfg.DETECTION_CONFIDENCE,
        min_tracking_confidence =cfg.TRACKING_CONFIDENCE,
    ) as pose:

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] Stream ended.")
                break

            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)

            metrics = {"torso_angle": 0, "aspect_ratio": 0, "com_y": 0,
                       "shoulder_mid": (0,0), "hip_mid": (0,0)}
            signals = {"is_horizontal": False, "is_wide_bbox": False,
                       "is_fast_drop": False, "velocity": 0, "consecutive": 0}

            if result.pose_landmarks:
                landmarks = result.pose_landmarks.landmark

                _, metrics, signals = detector.update(landmarks, frame_w, frame_h)

                if show_skeleton:
                    mp_draw.draw_landmarks(
                        frame,
                        result.pose_landmarks,
                        mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_styles.get_default_pose_landmarks_style(),
                    )

            now = time.time()
            fps = 1 / max(now - prev_time, 1e-6)
            prev_time = now

            if detector.fall_active and now < detector.alert_until:
                HUD.draw_fall_banner(frame)

            HUD.draw_status_panel(frame, metrics, signals, show_skeleton, detector.fall_active)
            HUD.draw_controls(frame)

            cv2.putText(frame, f"FPS: {fps:.1f}",
                        (frame_w - 110, 24), HUD.FONT, 0.6, HUD.GREEN, 2)

            cv2.imshow("Fall Detection", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                detector.reset()
                print("[INFO] Fall state reset.")
            elif key == ord("s"):
                show_skeleton = not show_skeleton

    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-time fall detection")
    parser.add_argument(
        "--source", default=0,
        help="Video source: camera index (0, 1, …), file path, or RTSP URL",
    )
    args = parser.parse_args()
    run(args.source)