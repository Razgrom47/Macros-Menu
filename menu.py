import tkinter as tk
import threading
import sys
import math
import json
from pynput import keyboard
from pynput.keyboard import Key, Controller
import subprocess

# pip install pycaw
from pycaw.pycaw import AudioUtilities

class OverlayMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # start hidden
        self.visible = False

        self.keyboard_controller = Controller()

        # Load menu config
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
        except:
            self.config = {
                "main": {},
                "settings": {}
            }

        # Extract palettes
        self.palettes = self.config["settings"].get("Palette", {}).get("options", {})
        self.current_palette_name = "black"  # default
        self.palette = self.palettes.get(self.current_palette_name, {})

        # Initialize values for adjustable settings
        self.values = {}
        self.app_exe_map = {
            "Chrome": "chrome.exe",
            "Spotify": "Spotify.exe",
            "Discord": "Discord.exe",
            "GameList": "GameList.exe",  # Adjust as needed
            "Something else": "something.exe"  # Adjust as needed
        }
        for menu_name, data in self.config["settings"].items():
            if menu_name != "Palette":
                opts = data.get("options", {})
                self.values[menu_name] = {k: 50 for k in opts.keys()}

        # Window setup
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.82)

        self.w = self.root.winfo_screenwidth()
        self.h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.w}x{self.h}+0+0")
        self.root.config(bg=self.palette["bg"])

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            bg=self.palette["bg"],
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # ── Dynamic sizing ───────────────────────────────────────────────────────
        self.center_x = self.w // 2
        self.center_y = self.h // 2
        self.screen_ref = min(self.w, self.h)

        self.radius_center = int(self.screen_ref * 0.175)  # ~80–160 px
        self.inner_radius = int(self.screen_ref * 0.20)  # inner ring edge
        self.outer_radius = int(self.screen_ref * 0.47)  # outer ring edge
        self.padding_angle = 5  # degrees (usually fine fixed)

        self.center_font_size = int(self.screen_ref * 0.018)  # "Main Menu", "Settings" etc.
        self.option_font_size = int(self.screen_ref * 0.014)  # arc labels
        self.corner_padding = int(self.screen_ref * 0.018)  # margin from edges
        self.button_padx = int(self.screen_ref * 0.024)
        self.button_pady = int(self.screen_ref * 0.016)
        self.button_font_size = int(self.screen_ref * 0.025)

        # Center hub
        self.center_circle = self.canvas.create_oval(
            self.center_x - self.radius_center, self.center_y - self.radius_center,
            self.center_x + self.radius_center, self.center_y + self.radius_center,
            fill=self.palette["center"],
            outline="",
            width=0
        )

        self.center_text = self.canvas.create_text(
            self.center_x, self.center_y,
            text="Main Menu",
            font=("Segoe UI", self.center_font_size, "bold"),
            fill=self.palette["text"],
            anchor="center"
        )

        # Donut hole mask
        self.inner_mask = self.canvas.create_oval(
            self.center_x - self.inner_radius, self.center_y - self.inner_radius,
            self.center_x + self.inner_radius, self.center_y + self.inner_radius,
            fill=self.palette["bg"],
            outline=""
        )

        # Build menus from config
        self.menus = {}

        # Build main menu
        if "main" in self.config:
            main_sub = self.config["main"]
            main_options = list(main_sub.keys())
            main_actions = [lambda o=opt: self.go_to_menu(o) for opt in main_options]
            self.menus['main'] = {'text': 'Main Menu', 'options': main_options, 'actions': main_actions}

        # Build settings menu
        if "settings" in self.config:
            settings_sub = self.config["settings"]
            settings_options = list(settings_sub.keys())
            settings_actions = [lambda o=opt: self.go_to_menu(o) for opt in settings_options]
            self.menus['settings'] = {'text': 'Settings', 'options': settings_options, 'actions': settings_actions}

        # Build submenus from config
        for group in ["main", "settings"]:
            if group in self.config:
                for menu_name, data in self.config[group].items():
                    opts = data.get("options", {})
                    if isinstance(opts, dict):
                        option_list = list(opts.keys())
                        if all(isinstance(opts[k], dict) for k in option_list):  # Palettes
                            actions = [lambda k=k: (self.change_palette(k), self.go_back()) for k in option_list]
                        else:
                            if group == "main":
                                actions = [lambda k=k, v=opts[k]: (self.hide(), self.simulate_shortcut(v)) for k in option_list]
                            else:  # settings adjustable
                                actions = [lambda k=k: self.set_selected(k) for k in option_list]
                        self.menus[menu_name] = {
                            'text': data.get("text", menu_name),
                            'options': option_list,
                            'actions': actions
                        }
                    elif isinstance(opts, list):
                        if len(opts) == 0:
                            self.menus[menu_name] = {
                                'text': data.get("text", menu_name),
                                'options': [],
                                'actions': []
                            }

        # Navigation stack
        self.menu_stack = ['main']
        self.current_menu = self.menus.get('main', {'text': 'Main Menu', 'options': [], 'actions': []})

        # Draw initial menu
        self.option_items = []
        self.option_texts = []
        self.draw_menu()

        # Side window for settings
        self.side_window = None
        self.option_labels = {}
        self.selected_option = None
        self.current_setting = None
        self.slider_var = None

        # Corner buttons
        self.settings_btn = tk.Button(
            self.root, text="⚙ Settings",
            font=("Segoe UI", self.button_font_size, "bold"),
            bg=self.palette["option"], fg=self.palette["text"],
            activebackground=self.palette["accent"], activeforeground="#000000",
            relief="flat", bd=0,
            padx=self.button_padx, pady=self.button_pady,
            command=self.open_settings
        )
        self.settings_btn.place(x=self.corner_padding, y=self.corner_padding)

        self.back_btn = tk.Button(
            self.root, text="⬅ Back",
            font=("Segoe UI", self.button_font_size, "bold"),
            bg=self.palette["option"], fg=self.palette["text"],
            activebackground=self.palette["accent"], activeforeground="#000000",
            relief="flat", bd=0,
            padx=self.button_padx, pady=self.button_pady,
            command=self.go_back
        )
        self.back_btn.place(x=self.corner_padding, y=self.h - self.corner_padding - int(self.screen_ref * 0.09))

        # Button hover effects
        for btn in [self.settings_btn, self.back_btn]:
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.palette["accent"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.palette["option"]))

        # Global hotkeys
        self.listener = keyboard.GlobalHotKeys({
            '<ctrl>+<alt>': self.toggle,
            '<esc>': self.hide,
            '<shift>+<esc>': self.quit_app
        })

        threading.Thread(target=self.listener.start, daemon=True).start()

    def get_current_brightness(self):
        try:
            import wmi
            c = wmi.WMI(namespace='wmi')
            brightness = c.WmiMonitorBrightness()[0].CurrentBrightness
            return brightness
        except:
            return 50

    def get_app_volume(self, app_name):
        exe = self.app_exe_map.get(app_name)
        if not exe:
            return 50
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name() == exe:
                return int(session.SimpleAudioVolume.GetMasterVolume() * 100)
        return 0  # not running

    def parse_key(self, token):
        token_upper = token.upper()
        if len(token) == 1:
            return token.lower()
        key_map = {
            "CTRL": Key.ctrl,
            "CONTROL": Key.ctrl,
            "SHIFT": Key.shift,
            "WIN": Key.cmd,
            "WINDOWS": Key.cmd,
            "SEARCHBAR": Key.cmd,
            "ALT": Key.alt,
            "ENTER": Key.enter,
            "RETURN": Key.enter,
            "PRINTSCREEN": Key.print_screen,
            "PRINT SCREEN": Key.print_screen,
            # Add more as needed
        }
        if token_upper in key_map:
            return key_map[token_upper]
        elif hasattr(Key, token.lower()):
            return getattr(Key, token.lower())
        return None

    def simulate_shortcut(self, shortcut_str):
        tokens = []
        i = 0
        while i < len(shortcut_str):
            if shortcut_str[i].isspace():
                i += 1
                continue
            if shortcut_str[i] == "'":
                j = shortcut_str.find("'", i + 1)
                if j == -1:
                    j = len(shortcut_str)
                text = shortcut_str[i + 1:j]
                tokens.append(('text', text))
                i = j + 1
            else:
                j = shortcut_str.find("+", i)
                if j == -1:
                    j = len(shortcut_str)
                key_str = shortcut_str[i:j].strip()
                if key_str:
                    key = self.parse_key(key_str)
                    if key:
                        tokens.append(('key', key))
                i = j + 1

        has_text = any(t[0] == 'text' for t in tokens)
        if has_text:
            for typ, val in tokens:
                if typ == 'key':
                    self.keyboard_controller.press(val)
                    self.keyboard_controller.release(val)
                else:
                    self.keyboard_controller.type(val)
        else:
            pressed = []
            for typ, val in tokens:
                if typ == 'key':
                    self.keyboard_controller.press(val)
                    pressed.append(val)
            for val in reversed(pressed):
                self.keyboard_controller.release(val)

    def draw_menu(self):
        self.canvas.itemconfig(self.center_text, text=self.current_menu['text'])
        self.clear_options()

        options = self.current_menu['options']
        num_options = len(options)
        if num_options == 0:
            return

        slice_angle = 360 / num_options

        for i, text in enumerate(options):
            start_angle_tk = (i * slice_angle) - 90 + (self.padding_angle / 2)
            extent_angle_tk = slice_angle - self.padding_angle

            item = self.canvas.create_arc(
                self.center_x - self.outer_radius, self.center_y - self.outer_radius,
                self.center_x + self.outer_radius, self.center_y + self.outer_radius,
                start=-start_angle_tk,
                extent=-extent_angle_tk,
                fill=self.palette["option"],
                outline="",
                width=0,
                style="pieslice",
                tags=f"option_{i}"
            )
            self.canvas.lower(item, self.inner_mask)

            mid_angle_degrees = start_angle_tk + (extent_angle_tk / 2)
            mid_angle_radians = math.radians(mid_angle_degrees)
            text_radius = (self.inner_radius + self.outer_radius) / 2
            pos_x = self.center_x + text_radius * math.cos(mid_angle_radians)
            pos_y = self.center_y + text_radius * math.sin(mid_angle_radians)

            text_item = self.canvas.create_text(
                pos_x, pos_y,
                text=text,
                font=("Segoe UI", self.option_font_size, "bold"),
                fill=self.palette["text"],
                anchor="center",
                tags=f"option_{i}"
            )
            self.canvas.lower(text_item, self.inner_mask)

            self.option_items.append(item)
            self.option_texts.append(text_item)

            self.canvas.tag_bind(f"option_{i}", "<Enter>", lambda e, idx=i: self.on_hover_enter(idx))
            self.canvas.tag_bind(f"option_{i}", "<Leave>", lambda e, idx=i: self.on_hover_leave(idx))
            self.canvas.tag_bind(f"option_{i}", "<Button-1>", lambda e, idx=i: self.current_menu['actions'][idx]())

        self.canvas.tag_raise(self.center_circle)
        self.canvas.tag_raise(self.center_text)

    def clear_options(self):
        for item in self.option_items:
            self.canvas.delete(item)
        for text in self.option_texts:
            self.canvas.delete(text)
        self.option_items = []
        self.option_texts = []

    def on_hover_enter(self, idx):
        self.canvas.itemconfig(self.option_items[idx], fill=self.palette["option_hover"])

    def on_hover_leave(self, idx):
        self.canvas.itemconfig(self.option_items[idx], fill=self.palette["option"])

    def go_to_menu(self, menu_name):
        if menu_name in self.menus:
            self.menu_stack.append(menu_name)
            self.current_menu = self.menus[menu_name]
            self.draw_menu()
            if menu_name in self.config["settings"] and menu_name != "Palette":
                self.current_setting = menu_name
                # Fetch current values
                for opt in self.current_menu['options']:
                    if menu_name == "Screen":
                        self.values[menu_name][opt] = self.get_current_brightness()
                    elif menu_name == "Volume":
                        self.values[menu_name][opt] = self.get_app_volume(opt)
                self.open_side_window(menu_name)
            if len(self.current_menu['options']) == 0:
                print(f"{self.current_menu['text']} pressed")
                self.root.after(100, self.go_back)  # Slight delay for visibility
        else:
            print(f"Menu {menu_name} not found")

    def open_side_window(self, menu_name):
        if self.side_window:
            self.side_window.destroy()
        self.side_window = tk.Toplevel(self.root)
        self.side_window.geometry(f"200x400+{self.w - 250}+{self.center_y - 200}")
        self.side_window.overrideredirect(True)
        self.side_window.attributes("-topmost", True)
        self.side_window.config(bg=self.palette["bg"])

        self.option_labels = {}
        options = self.current_menu['options']
        for opt in options:
            val = self.values[menu_name][opt]
            lab = tk.Label(self.side_window, text=f"{opt}: {val}", font=("Segoe UI", 12), bg=self.palette["bg"], fg=self.palette["text"])
            lab.pack(pady=5)
            self.option_labels[opt] = lab

        self.slider_var = tk.IntVar()
        self.slider = tk.Scale(self.side_window, from_=0, to=100, orient='horizontal', variable=self.slider_var,
                               command=self.on_slider_change, bg=self.palette["bg"], fg=self.palette["text"],
                               highlightbackground=self.palette["accent"])
        self.slider.pack(pady=10, padx=10)

        if options:
            self.set_selected(options[0])

    def set_selected(self, opt):
        if self.selected_option:
            self.option_labels[self.selected_option].config(bg=self.palette["bg"])
        self.selected_option = opt
        self.option_labels[opt].config(bg=self.palette["accent"])
        self.slider_var.set(self.values[self.current_setting][opt])

    def on_slider_change(self, val):
        if self.selected_option:
            val = int(val)
            self.values[self.current_setting][self.selected_option] = val
            self.option_labels[self.selected_option].config(text=f"{self.selected_option}: {val}")
            self.adjust_system(self.current_setting, self.selected_option, val)

    def adjust_system(self, setting, opt, val):
        if setting == "Screen" and opt == "Brightness":
            subprocess.run(['powershell.exe', f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{val})'])
        elif setting == "Volume":
            app_name = self.app_exe_map.get(opt, opt.lower() + ".exe")
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name() == app_name:
                    volume = session.SimpleAudioVolume
                    volume.SetMasterVolume(val / 100.0, None)

    def go_back(self):
        if self.side_window:
            self.side_window.destroy()
            self.side_window = None
            self.selected_option = None
            self.current_setting = None
        if len(self.menu_stack) > 1:
            self.menu_stack.pop()
            self.current_menu = self.menus[self.menu_stack[-1]]
            self.draw_menu()
        else:
            self.hide()

    def open_settings(self):
        current = self.menu_stack[-1]
        if current == 'settings':
            self.go_back()
        else:
            if current != 'main':
                self.go_to_menu('main')
            self.go_to_menu('settings')

    def change_palette(self, color):
        if color in self.palettes:
            self.current_palette_name = color
            self.palette = self.palettes[color]
            self.update_colors()

    def update_colors(self):
        self.root.config(bg=self.palette["bg"])
        self.canvas.config(bg=self.palette["bg"])
        self.canvas.itemconfig(self.center_circle, fill=self.palette["center"])
        self.canvas.itemconfig(self.center_text, fill=self.palette["text"])
        self.canvas.itemconfig(self.inner_mask, fill=self.palette["bg"])

        for item, text_item in zip(self.option_items, self.option_texts):
            self.canvas.itemconfig(item, fill=self.palette["option"])
            self.canvas.itemconfig(text_item, fill=self.palette["text"])

        self.settings_btn.config(
            bg=self.palette["option"], fg=self.palette["text"],
            activebackground=self.palette["accent"], activeforeground="#000000"
        )
        self.back_btn.config(
            bg=self.palette["option"], fg=self.palette["text"],
            activebackground=self.palette["accent"], activeforeground="#000000"
        )
        if self.side_window:
            self.side_window.config(bg=self.palette["bg"])
            for lab in self.option_labels.values():
                lab.config(bg=self.palette["bg"], fg=self.palette["text"])
            if self.selected_option:
                self.option_labels[self.selected_option].config(bg=self.palette["accent"])
            self.slider.config(bg=self.palette["bg"], fg=self.palette["text"], highlightbackground=self.palette["accent"])

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        if not self.visible:
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.root.lift)
            self.visible = True

    def hide(self):
        if self.visible:
            if self.side_window:
                self.side_window.destroy()
                self.side_window = None
                self.selected_option = None
                self.current_setting = None
            self.root.withdraw()
            self.visible = False

    def quit_app(self):
        self.hide()
        try:
            if hasattr(self, 'listener'):
                self.listener.stop()
        except:
            pass
        try:
            self.root.after(0, self.root.destroy)
        except:
            pass
        sys.exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        app = OverlayMenu()
        app.run()
    except KeyboardInterrupt:
        sys.exit(0)
