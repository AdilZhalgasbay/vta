import sys
import os
import time
import shutil
import argparse

import cv2
import numpy as np

CHARS = r'$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,"^`\'. '

RESET     = "\033[0m"
HOME      = "\033[H"
HIDE_CUR  = "\033[?25l"
SHOW_CUR  = "\033[?25h"
ALT_ENTER = "\033[?1049h"
ALT_EXIT  = "\033[?1049l"
CHAR_RATIO = 0.45
MAX_COLS   = 220
MAX_ROWS   = 55


def pixel_to_char(brightness):
    idx = int(brightness / 255 * (len(CHARS) - 1))
    return CHARS[idx]


def frame_to_ascii(bgr_frame, cols, rows):
    rgb  = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    rgb  = cv2.resize(rgb, (cols, rows), interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    lines = []
    for row in range(rows):
        parts = []
        for col in range(cols):
            r, g, b = int(rgb[row, col, 0]), int(rgb[row, col, 1]), int(rgb[row, col, 2])
            ch = pixel_to_char(float(gray[row, col]))
            parts.append(f"\033[38;2;{r};{g};{b}m{ch}")
        lines.append("".join(parts) + RESET)
    return "\n".join(lines)


def get_terminal_size():
    size = shutil.get_terminal_size(fallback=(120, 40))
    return size.columns, size.lines


def calc_ascii_size(vid_w, vid_h, term_cols, term_rows):
    max_rows = term_rows - 1
    cols = term_cols
    rows = int(vid_h * cols / vid_w * CHAR_RATIO)
    if rows > max_rows:
        rows = max_rows
        cols = int(vid_w * rows / vid_h / CHAR_RATIO)
    return max(1, cols), max(1, rows)


def optimal_terminal_size(vid_w, vid_h):
    cols = MAX_COLS
    rows = int(vid_h * cols / vid_w * CHAR_RATIO) + 1
    if rows > MAX_ROWS:
        rows = MAX_ROWS
        cols = int(vid_w * (rows - 1) / vid_h / CHAR_RATIO)
    return max(10, cols), max(5, rows)


def resize_terminal(cols, rows):
    sys.stdout.write(f"\033[8;{rows};{cols}t")
    sys.stdout.flush()
    time.sleep(0.25)


def play(video_path, fps_limit=None, loop=False, auto_resize=True):
    if not os.path.isfile(video_path):
        print(f"Ошибка: файл '{video_path}' не найден.", file=sys.stderr)
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Ошибка: не удаётся открыть '{video_path}'.", file=sys.stderr)
        sys.exit(1)

    vid_fps     = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frm   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid_w       = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    target_fps  = min(fps_limit or vid_fps, vid_fps)
    frame_delay = 1.0 / target_fps

    if auto_resize:
        want_cols, want_rows = optimal_terminal_size(vid_w, vid_h)
        print(f"Изменяю окно: {want_cols}×{want_rows}...", flush=True)
        resize_terminal(want_cols, want_rows)

    sys.stdout.write(ALT_ENTER + HIDE_CUR)
    sys.stdout.flush()

    frame_idx = 0
    try:
        while True:
            ret, bgr = cap.read()
            if not ret:
                if loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame_idx = 0
                    continue
                break

            t_start = time.perf_counter()

            term_cols, term_rows = get_terminal_size()
            ascii_cols, ascii_rows = calc_ascii_size(vid_w, vid_h, term_cols, term_rows)
            ascii_frame = frame_to_ascii(bgr, ascii_cols, ascii_rows)

            current_s  = frame_idx / vid_fps
            duration_s = total_frm / vid_fps
            bar = f"  {current_s:.1f}s / {duration_s:.1f}s  |  {target_fps:.0f} FPS  |  {ascii_cols}×{ascii_rows}  |  Ctrl+C = стоп  "
            bar = bar[:term_cols]

            sys.stdout.write(HOME + ascii_frame + f"\n\033[7m{bar:<{term_cols}}{RESET}")
            sys.stdout.flush()

            frame_idx += 1

            elapsed = time.perf_counter() - t_start
            sleep_t = frame_delay - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sys.stdout.write(ALT_EXIT + SHOW_CUR)
        sys.stdout.flush()
        print(f"\nОстановлено на кадре {frame_idx}/{total_frm}")


def main():
    parser = argparse.ArgumentParser(description="Видео → цветной ASCII-арт в терминале")
    parser.add_argument("video")
    parser.add_argument("--fps",       type=float, default=None)
    parser.add_argument("--loop",      action="store_true")
    parser.add_argument("--no-resize", action="store_true")
    args = parser.parse_args()
    play(args.video, fps_limit=args.fps, loop=args.loop, auto_resize=not args.no_resize)


if __name__ == "__main__":
    main()
