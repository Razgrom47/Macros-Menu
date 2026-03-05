import tkinter as tk
import threading
import sys
import math
import json
from pynput import keyboard

class OverlayMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()           # start hidden
        self.visible = False

        # Load color palettes
        try:
            with open("palettes.json", "r") as f:
                self.palettes = json.load(f)
            self.current_palette_name = "black"  # default
            self.palette = self.palettes.get(self.current_palette_name, self.palettes["black"])
        except:
            self.palettes = {
                "blue": {
                    "bg": "#1e1e2e",
                    "overlay": "rgba(30, 30, 46, 0.88)",
                    "center": "#89b4fa",
                    "option": "#45475a",
                    "option_hover": "#89b4fa",
                    "text": "#cdd6f4",
                    "accent": "#89b4fa"
                },
                "green": {
                    "bg": "#162e1e",
                    "overlay": "rgba(22, 46, 30, 0.88)",
                    "center": "#a6e3a1",
                    "option": "#354a3e",
                    "option_hover": "#a6e3a1",
                    "text": "#d4f4cd",
                    "accent": "#a6e3a1"
                },
                "black": {
                    "bg": "#11111b",
                    "overlay": "rgba(17, 17, 27, 0.88)",
                    "center": "#6c7086",
                    "option": "#313244",
                    "option_hover": "#6c7086",
                    "text": "#cdd6f4",
                    "accent": "#6c7086"
                }
            }
            self.current_palette_name = "black"
            self.palette = self.palettes["black"]

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

        self.radius_center    = int(self.screen_ref * 0.175)      # ~80–160 px
        self.inner_radius     = int(self.screen_ref * 0.20)       # inner ring edge
        self.outer_radius     = int(self.screen_ref * 0.47)       # outer ring edge
        self.padding_angle    = 5                                 # degrees (usually fine fixed)

        self.center_font_size = int(self.screen_ref * 0.018)      # "Main Menu", "Settings" etc.
        self.option_font_size = int(self.screen_ref * 0.014)      # arc labels
        self.corner_padding   = int(self.screen_ref * 0.018)      # margin from edges
        self.button_padx      = int(self.screen_ref * 0.024)
        self.button_pady      = int(self.screen_ref * 0.016)
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

        # Menu definitions
        self.menus = {
            'main': {
                'text': "Main Menu",
                'options': ["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"],
                'actions': []
            },
            'settings': {
                'text': "Settings",
                'options': ["Screen", "Palettes"],
                'actions': []
            },
            'palettes': {
                'text': "Color Palette",
                'options': list(self.palettes.keys()),
                'actions': []
            }
        }

        # Assign actions
        self.menus['main']['actions'] = [lambda t=t: print(f"Selected: {t}") for t in self.menus['main']['options']]
        self.menus['settings']['actions'] = [lambda: print("screen pressed"), lambda: self.go_to_menu('palettes')]
        self.menus['palettes']['actions'] = [lambda c=c: self.change_palette(c) for c in self.menus['palettes']['options']]

        # Navigation stack
        self.menu_stack = ['main']
        self.current_menu = self.menus['main']

        # Draw initial menu
        self.option_items = []
        self.option_texts = []
        self.draw_menu()

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
            '0':         self.toggle,
            '<esc>':     self.hide,
            '<shift>+<esc>': self.quit_app
        })

        threading.Thread(target=self.listener.start, daemon=True).start()

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

            self.canvas.tag_bind(f"option_{i}", "<Enter>",   lambda e, idx=i: self.on_hover_enter(idx))
            self.canvas.tag_bind(f"option_{i}", "<Leave>",   lambda e, idx=i: self.on_hover_leave(idx))
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
        self.menu_stack.append(menu_name)
        self.current_menu = self.menus[menu_name]
        self.draw_menu()

    def go_back(self):
        if len(self.menu_stack) > 1:
            self.menu_stack.pop()
            self.current_menu = self.menus[self.menu_stack[-1]]
            self.draw_menu()
        else:
            self.hide()

    def open_settings(self):
        current = self.menu_stack[-1]
        if current == 'palettes':
            self.go_back()
        elif current == 'main':
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
            self.root.after(0, self.root.withdraw)
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