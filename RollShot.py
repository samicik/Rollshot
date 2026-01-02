import mss
import pyautogui
from PIL import Image, ImageTk
import numpy as np
import cv2
import time
import tkinter as tk
from tkinter import messagebox
import keyboard
import os
import json
import threading
import subprocess
import pystray
import sys

# Renkler (Logo uyumlu)
DARK_BLUE = '#1e2a4a'
LIGHT_BLUE = '#4da6e0'
WHITE = '#ffffff'
GRAY = '#7a8a9a'

# Yollar
APP_DIR = r"C:\Rollshot"
SS_DIR = os.path.join(APP_DIR, "SS")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
def resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

ICON_FILE = resource_path("rs.png")
BACK_FILE = resource_path("back.png")

is_running = False
tray_icon = None

def setup_folders():
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(SS_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f)

def first_run_check():
    config = load_config()
    if not config.get("installed"):
        root = tk.Tk()
        root.withdraw()
        
        win = tk.Toplevel(root)
        win.title("Rollshot")
        win.geometry("500x400")
        win.resizable(False, False)
        win.configure(bg=DARK_BLUE)
        
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 250
        y = (win.winfo_screenheight() // 2) - 200
        win.geometry(f"+{x}+{y}")
        
        # Canvas
        canvas = tk.Canvas(win, width=500, height=400, bg=DARK_BLUE, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        
        # Arka plan watermark (sol üst köşeye kaymış, silik)
        try:
            back_file = BACK_FILE
            bg_img = Image.open(back_file)
            bg_img = bg_img.resize((700, 700), Image.Resampling.LANCZOS)
            bg_img = bg_img.convert("RGBA")
            alpha = bg_img.split()[3]
            alpha = alpha.point(lambda p: int(p * 0.12))
            bg_img.putalpha(alpha)
            bg_base = Image.new("RGBA", bg_img.size, DARK_BLUE)
            bg_combined = Image.alpha_composite(bg_base, bg_img)
            bg_photo = ImageTk.PhotoImage(bg_combined)
            canvas.create_image(-20, -20, image=bg_photo, anchor='nw')
            canvas.bg_photo = bg_photo
        except:
            pass
        
        # Üst logo (küçük ve net)
        try:
            logo_img = Image.open(ICON_FILE)
            logo_img = logo_img.resize((110, 110), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            canvas.create_image(250, 80, image=logo_photo)
            canvas.logo_photo = logo_photo
        except:
            canvas.create_text(250, 80, text="RS", font=("Segoe UI", 40, "bold"), fill=LIGHT_BLUE)
        
        # Kısayol kutusu
        canvas.create_rectangle(170, 155, 330, 200, fill='#2a3a5a', outline=LIGHT_BLUE, width=2)
        canvas.create_text(250, 177, text="Ctrl+PrtScrn", font=("Consolas", 18, "bold"), fill=WHITE)
        
        # Adımlar
        steps_text = "Kısayola bas  ›  Bölge seç  ›  Fareyi bırak  ›  Tamam!"
        canvas.create_text(250, 240, text=steps_text, font=("Segoe UI", 11), fill=WHITE)
        
        # Alt bilgi
        canvas.create_text(250, 280, text="Otomatik kaydeder ve klasörü açar", 
                          font=("Segoe UI", 10), fill=GRAY)
        canvas.create_text(250, 305, text="mimsami@gmail.com", 
                          font=("Segoe UI", 9), fill=GRAY)
        
        # Başla butonu
        btn = tk.Button(win, text="BAŞLA", font=("Segoe UI", 11, "bold"),
                       bg=LIGHT_BLUE, fg=WHITE, width=18, pady=8,
                       relief='flat', cursor='hand2', activebackground='#3a96d0',
                       activeforeground=WHITE, command=win.destroy)
        canvas.create_window(250, 355, window=btn)
        
        win.attributes('-topmost', True)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        root.wait_window(win)
        root.destroy()
        
        config["installed"] = True
        save_config(config)
def select_region():
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.attributes('-alpha', 0.3)
    root.attributes('-topmost', True)
    root.configure(bg='gray')
    
    canvas = tk.Canvas(root, cursor="cross", bg='gray', highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    
    label = tk.Label(root, text="BÖLGE SEÇİN  •  ESC iptal", font=("Segoe UI", 22, "bold"), 
                     bg="gray", fg="white")
    label.place(relx=0.5, rely=0.05, anchor="center")
    
    result = {"region": None}
    start = {"x": 0, "y": 0}
    rect = None
    
    def on_press(event):
        start["x"] = event.x
        start["y"] = event.y
    
    def on_drag(event):
        nonlocal rect
        if rect:
            canvas.delete(rect)
        rect = canvas.create_rectangle(start["x"], start["y"], event.x, event.y, 
                                        outline=LIGHT_BLUE, width=3)
    
    def on_release(event):
        x1 = min(start["x"], event.x)
        y1 = min(start["y"], event.y)
        x2 = max(start["x"], event.x)
        y2 = max(start["y"], event.y)
        result["region"] = (x1, y1, x2, y2)
        root.destroy()
    
    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", lambda e: root.destroy())
    
    root.mainloop()
    return result["region"]

def images_are_same(img1, img2, threshold=0.99):
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    if arr1.shape != arr2.shape:
        return False
    diff = np.abs(arr1.astype(int) - arr2.astype(int))
    similarity = 1 - (np.sum(diff) / (arr1.size * 255))
    return similarity > threshold

def find_overlap(img1, img2):
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    template = arr1[-200:, :]
    result = cv2.matchTemplate(arr2, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val > 0.8:
        return max_loc[1] + 200
    return 200

def stitch_images(images):
    if not images:
        return None
    result = images[0]
    for i in range(1, len(images)):
        overlap = find_overlap(result, images[i])
        img2_cropped = images[i].crop((0, overlap, images[i].width, images[i].height))
        new_height = result.height + img2_cropped.height
        new_img = Image.new('RGB', (result.width, new_height))
        new_img.paste(result, (0, 0))
        new_img.paste(img2_cropped, (0, result.height))
        result = new_img
    return result

def open_folder():
    subprocess.Popen(f'explorer "{SS_DIR}"')

def take_scrollshot():
    global is_running
    if is_running:
        return
    is_running = True
    
    region = select_region()
    
    if region is None or region[2] - region[0] < 50 or region[3] - region[1] < 50:
        is_running = False
        return
    
    time.sleep(1.5)
    screenshots = []
    
    with mss.mss() as sct:
        monitor = {"top": region[1], "left": region[0], 
                   "width": region[2]-region[0], "height": region[3]-region[1]}
        prev_img = None
        
        for i in range(50):
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            if prev_img and images_are_same(prev_img, img):
                break
            
            screenshots.append(img.copy())
            prev_img = img.copy()
            pyautogui.scroll(-800)
            time.sleep(0.5)
    
    if screenshots:
        final = stitch_images(screenshots)
        if final:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"Rollshot_{timestamp}.png"
            filepath = os.path.join(SS_DIR, filename)
            final.save(filepath)
            open_folder()
    
    is_running = False

def uninstall():
    try:
        root = tk.Tk()
        root.withdraw()
        root.lift()
        root.attributes('-topmost', True)
        root.focus_force()
        
        result = messagebox.askyesno("Rollshot Kaldır", 
            "Rollshot'ı kaldırmak istediğinize emin misiniz?\n\n"
            "Ayarlar silinecek, ekran görüntüleri korunacak.",
            parent=root)
        
        root.destroy()
        
        if result:
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            quit_app()
    except:
        quit_app()

def create_tray_icon():
    try:
        icon_img = Image.open(ICON_FILE)
        icon_img = icon_img.resize((64, 64), Image.Resampling.LANCZOS)
    except:
        icon_img = Image.new('RGB', (64, 64), color=DARK_BLUE)
    
    menu = pystray.Menu(
        pystray.MenuItem("Rollshot", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Screenshot Al", lambda: threading.Thread(target=take_scrollshot).start()),
        pystray.MenuItem("Klasörü Aç", lambda: open_folder()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Kaldır", lambda: threading.Thread(target=uninstall).start()),
        pystray.MenuItem("Çıkış", quit_app)
    )
    
    return pystray.Icon("Rollshot", icon_img, "Rollshot • Ctrl+PrtSc", menu)

def quit_app(icon=None):
    keyboard.unhook_all()
    if icon:
        icon.stop()
    os._exit(0)

def on_hotkey():
    threading.Thread(target=take_scrollshot).start()

def main():
    global tray_icon
    setup_folders()
    first_run_check()
    keyboard.add_hotkey('ctrl+print_screen', on_hotkey)
    tray_icon = create_tray_icon()
    tray_icon.run()

if __name__ == "__main__":
    main()
