import cv2
import time
import os
import json
import threading
import requests
import pyautogui
import tkinter as tk
from tkinter import ttk, messagebox
CONFIG_FILE = "config.json"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass

    return {
        "telegram_token": "",
        "telegram_chat": "",
        "telegram_enabled": False,
        "save_interval": 5,
        "telegram_interval": 120,
        "cam_folder": "CAM_captured",
        "scr_folder": "SCR_captured"
    }


def save_config():
    data = {
        "telegram_token": token_entry.get(),
        "telegram_chat": chat_entry.get(),
        "telegram_enabled": telegram_var.get(),
        "save_interval": save_entry.get(),
        "telegram_interval": telegram_interval_entry.get(),
        "cam_folder": cam_folder_entry.get(),
        "scr_folder": scr_folder_entry.get()
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


config = load_config()


# ---------------- Settings ----------------
save_interval = 5
telegram_interval = 120

cam_folder = "CAM_captured"
scr_folder = "SCR_captured"

MOTION_THRESHOLD_AREA = 250
DIFF_THRESHOLD = 20

running = False
send_telegram_enabled = False

telegram_token = ""
telegram_chat = ""

last_save = 0
last_telegram = 0

saved_frames = []

last_cam_path = None
last_scr_path = None
motion_since_last_telegram = False  # ← اضافه شد


os.makedirs(cam_folder, exist_ok=True)
os.makedirs(scr_folder, exist_ok=True)


# ---------------- Telegram ----------------
def send_message(text):
    if not send_telegram_enabled:
        return

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": telegram_chat,
            "text": text
        })
    except Exception as e:
        print(e)


def send_photo(path):
    if not send_telegram_enabled:
        return

    url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"

    try:
        with open(path, "rb") as photo:
            requests.post(url, data={
                "chat_id": telegram_chat
            }, files={
                "photo": photo
            })
    except Exception as e:
        print(e)


# ---------------- Capture ----------------
def save_camera_image(path, frame):
    cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 35])


def take_screenshot(path):
    img = pyautogui.screenshot()
    img.save(path, "JPEG", quality=10)


# ---------------- Motion ----------------
def detect_motion(frame, last_frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if last_frame is None:
        return gray, False

    delta = cv2.absdiff(last_frame, gray)
    thresh = cv2.threshold(delta, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, 2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in contours:
        if cv2.contourArea(c) >= MOTION_THRESHOLD_AREA:
            return gray, True

    return gray, False


# ---------------- Camera Loop ----------------
def camera_loop():
    global running
    global last_save, last_telegram
    global last_cam_path, last_scr_path
    global motion_since_last_telegram  # ← اضافه شد

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        messagebox.showerror("Error", "Camera not found")
        return

    last_frame = None

    while running:

        ret, frame = cap.read()
        if not ret:
            break

        last_frame, motion = detect_motion(frame, last_frame)
        now = time.time()

        if motion and now - last_save >= save_interval:

            ts = time.strftime("%Y-%m-%d_%H-%M-%S")

            last_cam_path = os.path.join(cam_folder, f"cam_{ts}.jpg")
            last_scr_path = os.path.join(scr_folder, f"screen_{ts}.jpg")

            save_camera_image(last_cam_path, frame)
            take_screenshot(last_scr_path)

            saved_frames.append(last_cam_path)
            if len(saved_frames) > 20:
                saved_frames.pop(0)

            last_save = now
            motion_since_last_telegram = True  # ← اضافه شد

        # -------- Telegram send --------
        if send_telegram_enabled and now - last_telegram >= telegram_interval:
            if motion_since_last_telegram:  # ← فقط اگر حرکت جدید بود بفرست
                send_message("🚨 Motion detected")

                if last_cam_path:
                    send_photo(last_cam_path)

                if last_scr_path:
                    send_photo(last_scr_path)

                motion_since_last_telegram = False  # ← ریست کن
                last_telegram = now

    cap.release()
    cv2.destroyAllWindows()


# ---------------- GUI ----------------
def start():
    global running
    global save_interval
    global telegram_token, telegram_chat, send_telegram_enabled
    global cam_folder, scr_folder
    global telegram_interval

    try:
        save_interval = int(save_entry.get())
        telegram_interval = int(telegram_interval_entry.get())
    except:
        messagebox.showerror("Error", "Invalid numbers")
        return

    cam_folder = cam_folder_entry.get()
    scr_folder = scr_folder_entry.get()

    os.makedirs(cam_folder, exist_ok=True)
    os.makedirs(scr_folder, exist_ok=True)

    telegram_token = token_entry.get()
    telegram_chat = chat_entry.get()
    send_telegram_enabled = telegram_var.get()

    if send_telegram_enabled and (telegram_token == "" or telegram_chat == ""):
        messagebox.showwarning("Error", "Telegram info required")
        return
    save_config()
    if running:
        return

    running = True

    threading.Thread(target=camera_loop, daemon=True).start()

    status_label.configure(text="Running...")


def stop():
    global running
    running = False
    status_label.configure(text="Stopped")


def test_telegram():
    if token_entry.get() == "" or chat_entry.get() == "":
        messagebox.showwarning("Error", "Enter Telegram info")
        return

    url = f"https://api.telegram.org/bot{token_entry.get()}/sendMessage"

    requests.post(url, data={
        "chat_id": chat_entry.get(),
        "text": "✅ Test message"
    })

    messagebox.showinfo("Telegram", "Sent")


# ---------------- UI ----------------
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Motion Security System")
root.geometry("520x600")
root.resizable(False, False)


title = ctk.CTkLabel(
    root,
    text="🔒 Motion Security",
    font=("Arial", 24, "bold")
)
title.pack(pady=20)


# -------- Telegram --------
frame1 = ctk.CTkFrame(root)
frame1.pack(padx=20, pady=10, fill="x")

ctk.CTkLabel(frame1, text="Bot Token").pack(pady=5)
token_entry = ctk.CTkEntry(frame1, width=400, show="*")
token_entry.pack()
token_entry.insert(0, config["telegram_token"])

ctk.CTkLabel(frame1, text="Chat ID").pack(pady=5)
chat_entry = ctk.CTkEntry(frame1, width=400, show="*")
chat_entry.pack()
chat_entry.insert(0, config["telegram_chat"])

telegram_var = tk.BooleanVar(value=config["telegram_enabled"])

ctk.CTkCheckBox(
    frame1,
    text="Enable Telegram",
    variable=telegram_var
).pack(pady=10)


# -------- Settings --------
frame2 = ctk.CTkFrame(root)
frame2.pack(padx=20, pady=10, fill="x")

ctk.CTkLabel(frame2, text="Save interval (sec)").pack()
save_entry = ctk.CTkEntry(frame2)
save_entry.insert(0, str(config["save_interval"]))
save_entry.pack()

ctk.CTkLabel(frame2, text="Telegram interval (sec)").pack()
telegram_interval_entry = ctk.CTkEntry(frame2)
telegram_interval_entry.insert(0, str(config["telegram_interval"]))
telegram_interval_entry.pack()

ctk.CTkLabel(frame2, text="Camera folder").pack()
cam_folder_entry = ctk.CTkEntry(frame2)
cam_folder_entry.insert(0, config["cam_folder"])
cam_folder_entry.pack()

ctk.CTkLabel(frame2, text="Screen folder").pack()
scr_folder_entry = ctk.CTkEntry(frame2)
scr_folder_entry.insert(0, config["scr_folder"])
scr_folder_entry.pack()


# -------- Buttons --------
btn_frame = ctk.CTkFrame(root)
btn_frame.pack(pady=20)

ctk.CTkButton(btn_frame, text="🧪 Test", command=test_telegram).grid(row=0, column=0, padx=10)
ctk.CTkButton(btn_frame, text="▶ Start", command=start).grid(row=0, column=1, padx=10)
ctk.CTkButton(btn_frame, text="⏹ Stop", command=stop).grid(row=0, column=2, padx=10)


status_label = ctk.CTkLabel(root, text="Status: Stopped")
status_label.pack(pady=20)
def on_close():
    save_config()
    stop()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
