from typing import List, Dict, Optional, Any
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import time

initial_time = time.perf_counter()
last_scene_time = initial_time
binded = False
in_popup = False

# Load helper functions

def rgb(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def fade_in(win, alpha=0):
    if alpha < 1:
        alpha += 0.1
        win.attributes("-alpha", alpha)
        win.after(20, lambda: fade_in(win, alpha))

def create_popup(title: str, width=400, height=300):
    global in_popup
    win = tk.Toplevel(root)
    win.overrideredirect(True)  # remove OS window borders
    win.configure(bg="#0f0f1a")

    # Center window
    root.update_idletasks()
    rw = root.winfo_width()
    rh = root.winfo_height()

    x = root.winfo_x() + (rw // 2) - (width // 2)
    y = root.winfo_y() + (rh // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

    win.attributes("-alpha", 0)
    fade_in(win)

    # Outer frame (border effect)
    outer = tk.Frame(win, bg="#3a3a5a", padx=2, pady=2)
    outer.pack(fill="both", expand=True)

    # Inner frame
    inner = tk.Frame(outer, bg="#1c1c2e")
    inner.pack(fill="both", expand=True)

    # Title bar
    title_bar = tk.Frame(inner, bg="#2a2a4a", height=30)
    title_bar.pack(fill="x")

    tk.Label(
        title_bar,
        text=title,
        bg="#2a2a4a",
        fg="white",
        font=("Bell MT", 12, "bold")
    ).pack(side="left", padx=10)

    def close():
        global in_popup
        in_popup = False
        win.destroy()

    # Close button
    tk.Button(
        title_bar,
        text="✕",
        bg="#2a2a4a",
        fg="white",
        bd=0,
        command=close
    ).pack(side="right", padx=10)

    content = tk.Frame(inner, bg="#1c1c2e")
    content.pack(fill="both", expand=True, padx=10, pady=10)
    
    in_popup = True

    return win, content

def parse_script(path: str) -> List[Dict[str, str]]:
    with open(path, "r") as f:
        lines = [line.strip() for line in f]

    blocks = []
    current_block = []

    # Split into blocks by ----
    for line in lines:
        if line.startswith("----"):
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            if line:  # skip empty lines
                current_block.append(line)

    if current_block:
        blocks.append(current_block)

    result = []

    for block in blocks:
        if len(block) < 2:
            raise ValueError(f"Incomplete block: {block}")

        scene_name = block[0]

        if block[1].startswith("CHOICE:"):
            _, options = block[1].split(":")
            paths = options.split(",")

            result.append({
                "scene": scene_name,
                "choice": paths,
                "text": "\n".join(block[2:])
            })
            continue

        # Parse "Jack:Neutral, park daytime"
        header = block[1]

        # Split character/expression
        char_part, *context_part = header.split(",", 1)

        if ":" in char_part:
            name, expression = char_part.split(":")
        else:
            name, expression = char_part, ""

        context = []
        if context_part:
            context = context_part[0].replace(",", " ").split()

        # Remaining lines = dialog text
        text = "\n".join(block[2:])

        result.append({
            "scene": scene_name,
            "character": name.strip(),
            "expression": expression.strip(),
            "context": context,
            "text": text
        })

    return result

def get_environment_image(context: List[str]) -> ImageTk.PhotoImage:
    # example: ["park", "daytime"] → "./Assets/The-Park-Daylight.jpg"
    key = f"./Assets/The-{context[0].capitalize()}-{context[1].capitalize()}.jpg"
    return images[key]

def get_character_image(character: str, expression: str) -> ImageTk.PhotoImage:
    key = f"./Assets/{character}/{expression.lower()}.png"
    return images[key]

def load_manus(path: str) -> List["Scene"]:
    manus = parse_script(path)

    scene_meta = defaultdict(list)
    for d in manus:
        scene_meta[d["scene"]].append(d)

    manus = []
    for scene_name, dialogs_data in scene_meta.items():
        # assume all dialogs in a scene share the same context
        context = dialogs_data[0]["context"]

        environment = get_environment_image(context)

        dialogs = []
        for d in dialogs_data:
            if "choice" in d:
                dialogs.append(Dialog(None, "Choice", d['text'], d['choice']))
                continue
            is_narrator = d["character"].lower() == "narrator"
            if not is_narrator:
                char_img = get_character_image(d["character"], d["expression"])
            text = d['text']

            dialogs.append(Dialog(char_img if not is_narrator else None, d["character"], text))

        manus.append(
            Scene(
                canvas,
                name=scene_name,
                environment=environment,
                dialogs=dialogs
            )
        )
    
    return manus

# Load cache

class Dialog:
    __slots__ = ("char", "name", "text", "choice")
    def __init__(self, char: Optional[ImageTk.PhotoImage], name: str, text: str, choice: Optional[List[str]] = None) -> None:
        self.char = char
        self.name = name
        self.text = text
        self.choice = choice

class Scene:
    __slots__ = ("name", "environment", "dialogs", "cache", "canvas")
    def __init__(self, canvas: Optional[tk.Canvas] = None, /, *, name: str, environment: ImageTk.PhotoImage, dialogs: List[Dialog]) -> None:
        self.name = name
        self.environment = environment
        self.dialogs = dialogs
        self.cache = []
        self.canvas = None
        if canvas is not None:
            self.preload_dialogs(canvas)
    def preload_dialogs(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.cache.clear()
        for dialog in self.dialogs:
            char = dialog.char
            name = dialog.name
            text = dialog.text
            self.cache.append(
                lambda char=char, name=name, text=text: (
                    canvas.delete('all'),
                    draw_dialog(canvas, self.name, self.environment, char, name, text)
                )
            )
    def load(self, index: int) -> None:
        self.canvas.delete('all')
        self.cache[index]()

# Load topbar

def open_file(event=None):
    if in_popup:
        return
    f = filedialog.askopenfile(mode="r")
    if f is not None:
        global current_scene, current_dialog, active, manus, manus_index
        content = f.readlines()[0].split(",", 3)
        current_scene = int(content[0])
        current_dialog = int(content[1])
        manus_index = int(content[2])
        manus = list(manus_list[manus_index])
        scene = manus[current_scene]
        scene.load(current_dialog)
        if not active:
            active = True
        f.close()

def save_file(event=None):
    if in_popup:
        return
    if not active:
        messagebox.showwarning("Saving Inactive Game", "You cannot save a game without having played it.")
        return
    f = filedialog.asksaveasfile(mode="w")
    if f is not None and binded and active:
        f.write(f"{current_scene}, {current_dialog}, {manus_index}")
        f.close()

def set_scene(event=None):
    if in_popup:
        return
    
    global active
    win, content = create_popup("Fast Forward", 420, 320)

    def styled_entry(label_text, default):
        frame = tk.Frame(content, bg="#1c1c2e")
        frame.pack(pady=5, fill="x")

        tk.Label(
            frame,
            text=label_text,
            width=15,
            anchor="w",
            bg="#1c1c2e",
            fg="white",
            font=("Bell MT", 12)
        ).pack(side="left")

        entry = tk.Entry(
            frame,
            bg="#2e2e4f",
            fg="white",
            insertbackground="white",
            relief="flat"
        )
        entry.pack(side="right", fill="x", expand=True)

        entry.insert(0, default)

        return entry

    manus_entry = styled_entry("Manus:", manus_names[manus_index])
    scene_entry = styled_entry("Scene:", manus[current_scene].name)
    dialog_entry = styled_entry("Dialog:", current_dialog)

    def apply():
        global manus_index, manus, current_scene, current_dialog, active, in_popup

        try:
            m = manus_entry.get()
            s = scene_entry.get()
            d = dialog_entry.get()

            m = int(m) if m.isnumeric() else choice_to_manus_index[m.strip().lower()]

            if s.isnumeric():
                s = int(s)
            else:
                scene_name = s.strip().lower()
                for i, dct in enumerate(manus_list[m]):
                    if dct.name.strip().lower() == scene_name:
                        s = i
                        break
                else:
                    raise RuntimeError("Could not locate the scene in the given manus.")

            d = int(d)

        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        manus_index = m
        manus = list(manus_list[manus_index])

        current_scene = s
        current_dialog = d

        manus[current_scene].load(current_dialog)

        if active == False:
            active = True

        win.destroy()
        in_popup = False

    tk.Button(
        content,
        text="Jump",
        font=("Bell MT", 14, "bold"),
        bg="#4a4a7a",
        fg="white",
        relief="flat",
        command=apply
    ).pack(pady=15)

def goto_menu(event=None):
    if in_popup:
        return
    
    global current_scene, current_dialog, manus_index, manus
    current_scene = 0
    current_dialog = 0
    manus = manus_list[0]
    manus_index = 0
    load_menu(canvas)

def init_topbar(root: tk.Tk) -> None:
    #THE MENUBAR
    #create a frame for the menubar
    menuframe = ttk.Frame(root)
    menuframe.grid(column=1, row=1)
    #create the menubar
    menubar = tk.Menu(menuframe)
    #menu drop-downs
    menubar_file = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(menu=menubar_file, label='File')
    #menu options for "file" menu
    menubar_file.add_command(label='Open', accelerator="Control + O", command=open_file)
    menubar_file.add_command(label='Save', accelerator="Control + S", command=save_file)
    menubar_file.add_separator()
    menubar_file.add_command(label="Fast Forward", accelerator="Control + F", command=set_scene)
    menubar_file.add_command(label="Go To Menu", accelerator="Control + M", command=goto_menu)
    menubar_file.add_separator()
    menubar_file.add_command(label='Exit', command=root.quit)
    #add menu bar to root window
    root.config(menu=menubar)

# Load resources

root = tk.Tk()
root.title("Visual Novel")
root.geometry("800x600")

topbar = ttk.Frame(root)
topbar.grid(column=0, row=0, sticky=(tk.W,tk.E,tk.N))

width, height = 800, 600
canvas = tk.Canvas(root, width=width, height=height)
canvas.grid(column=0, columnspan=2, row=0, rowspan=2)

resize_after_id = None

def get_scaled_size(win_w, win_h):
    target_ratio = 800 / 600

    if win_w / win_h > target_ratio:
        # window too wide
        new_h = win_h
        new_w = int(win_h * target_ratio)
    else:
        # window too tall
        new_w = win_w
        new_h = int(win_w / target_ratio)

    return new_w, new_h

def apply_resize():
    global width, height, manus

    win_w = root.winfo_width()
    win_h = root.winfo_height()

    width, height = get_scaled_size(win_w, win_h)

    canvas.config(width=width, height=height)

    # center canvas (letterbox effect)
    canvas.place(
        x=(win_w - width) // 2,
        y=(win_h - height) // 2
    )

    #if not active:
    #    load_menu(canvas)

    adjust_images()
    load_all_manus()

    manus = manus_list[manus_index]

    if active and not in_popup:
        manus[current_scene].load(current_dialog)

def on_resize(event=None):
    global resize_after_id

    if abs(root.winfo_width() - width) < 1 or abs(root.winfo_height() - height) < 1:
        return

    if resize_after_id:
        root.after_cancel(resize_after_id)

    resize_after_id = root.after(200, apply_resize)

def toggle_fullscreen(event=None):
    root.attributes("-fullscreen", not root.attributes("-fullscreen"))

root.bind("<F11>", toggle_fullscreen)
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
root.bind("<Configure>", on_resize)

def get_char_pos(name):
    if name == "Jack":
        return width - int(width * 0.25), height - int(height * 0.5)
    if name == "Sophia":
        return width - int(width * 0.3), height - int(height * 0.6)

WAIT_TIME = 1
TEXT_SPEED = 0.025

THIS_PATH = "./"
ASSETS = "Assets/"
MANUS = ASSETS + "manus/"
PARK = ASSETS + "The-Park-Daylight.jpg"
BAR = ASSETS + "The-Bar-Daylight.jpg"
ROOM = ASSETS + "The-Room-Daylight.jpg"
JACK = ASSETS + "Jack/"
SOPHIA = ASSETS + "Sophia/"
BLUSHING = "blushing.png"
EMBARASSED = "embarrassed.png"
FLUSTERED = "flustered.png"
HAPPY = "happy.png"
NEUTRAL = "neutral.png"
SAD = "sad.png"
SERIOUS = "serious.png"
SOFT_SMILE = "soft_smile.png"
SURPRISED = "surprised.png"
UPSET = "upset.png"

IMAGE_PATHS = [
    THIS_PATH + PARK,
    THIS_PATH + BAR,
    THIS_PATH + ROOM,
    THIS_PATH + JACK + BLUSHING,
    THIS_PATH + JACK + EMBARASSED,
    THIS_PATH + JACK + FLUSTERED, 
    THIS_PATH + JACK + HAPPY, 
    THIS_PATH + JACK + NEUTRAL,
    THIS_PATH + JACK + SAD,
    THIS_PATH + JACK + SERIOUS,
    THIS_PATH + JACK + SOFT_SMILE,
    THIS_PATH + SOPHIA + BLUSHING,
    THIS_PATH + SOPHIA + HAPPY,
    THIS_PATH + SOPHIA + SAD,
    THIS_PATH + SOPHIA + SURPRISED,
    THIS_PATH + SOPHIA + UPSET,
]

raw_images = {}
images = {}

def preload_images():
    for image in IMAGE_PATHS:
        raw_images[image] = Image.open(image)

def adjust_images():
    sizes = [
        (width, height),
        (int(width * 0.1875), int(height * 0.416)),
        (int(width * 0.3125), int(height * 0.75))
    ]
    for i, image in enumerate(IMAGE_PATHS):
        if i < 3:
            size = sizes[0]
        elif i < 11:
            size = sizes[1]
        else:
            size = sizes[2]
        image_pil = raw_images[image].resize(size)
        image_tk = ImageTk.PhotoImage(image_pil)
        images[image] = image_tk

preload_images()
adjust_images()

def round_rectangle(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int=25, **kwargs: Any):    
    points = (x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1)
    return canvas.create_polygon(points, **kwargs, smooth=True)

def typewriter(canvas, text_id, full_text, index=0):
    if index > len(full_text):
        return

    canvas.itemconfig(text_id, text=full_text[:index])

    canvas.after(int(TEXT_SPEED * 1000),
                 lambda: typewriter(canvas, text_id, full_text, index + 1))

def draw_dialog(canvas: tk.Canvas, scene_name: str, environment: ImageTk.PhotoImage, char: Optional[ImageTk.PhotoImage], name: str, text: str) -> None:
    canvas.create_image(0, 0, anchor="nw", image=environment)
    if char is not None:
        canvas.create_image(*get_char_pos(name), anchor="nw", image=char)
    box_height = int(height * 0.25)
    round_rectangle(
        canvas,
        0,
        height - box_height,
        width,
        height,
        25,
        fill=rgb(160,180,70),
        outline="white"
    )
    box_top = height - box_height
    padding = int(box_height * 0.1)
    text_renderer = canvas.create_text(
        10, box_top + padding,
        anchor = "nw",
        fill = rgb(50, 50, 75), 
        font = ("Bell MT", 15),
        text = f"{name}:\n",
    )
    font_size = max(12, int(height * 0.025))
    canvas.create_text(
        width//2 + 2, 42,
        anchor = "center",
        fill = rgb(0, 140, 25), 
        font = ("Script MT Bold", font_size),
        text = f"{manus_names[manus_index]} - {scene_name}",
    )
    canvas.create_text(
        width//2, 40,
        anchor = "center",
        fill = rgb(100, 240, 125), 
        font = ("Script MT Bold", font_size),
        text = f"{manus_names[manus_index]} - {scene_name}",
    )

    full_text = f"{name}:\n{text}"

    typewriter(canvas, text_renderer, full_text)

# Load manus

def load_all_manus():
    manus1.clear()
    manus1.extend(load_manus(manus_path[0]))
    manus2.clear()
    manus2.extend(load_manus(manus_path[1])) # Run after
    manus3.clear()
    manus3.extend(load_manus(manus_path[2])) # Walk away
    manus4.clear()
    manus4.extend(load_manus(manus_path[3]))
    manus5.clear()
    manus5.extend(load_manus(manus_path[4]))
    manus6.clear()
    manus6.extend(load_manus(manus_path[5]))
    manus7.clear()
    manus7.extend(load_manus(manus_path[6]))
    manus8.clear()
    manus8.extend(load_manus(manus_path[7]))

    manus_list.clear()
    manus_list.extend([
        manus1, manus2, manus3, manus4, manus5, manus6, manus7, manus8
    ])

manus1 = []
manus2 = []
manus3 = []
manus4 = []
manus5 = []
manus6 = []
manus7 = []
manus8 = []

manus_list = []

manus_path = [
    THIS_PATH + MANUS + "entry",
    THIS_PATH + MANUS + "opt1",
    THIS_PATH + MANUS + "opt2",
    THIS_PATH + MANUS + "opt3",
    THIS_PATH + MANUS + "opt4",
    THIS_PATH + MANUS + "opt5",
    THIS_PATH + MANUS + "opt6",
    THIS_PATH + MANUS + "opt7"
]

load_all_manus()

manus_names = [
    "Just Another Day",
    "Deep In Love",
    "A Depressing Ending",
    "Another Way Around",
    "Deep Dark",
    "Long Run",
    "So Long Ago",
    "Only Easter"
]

choice_to_manus_index = {
    "just another day": 0,
    "deep in love": 1,
    "a depressing ending": 2,
    "another way around": 3,
    "deep dark": 4,
    "long run": 5,
    "so long ago": 6,
    "only easter": 7,
    "entry": 0,
    "run after": 1,
    "walk away": 2,
    "comfort": 3,
    "neglect": 4,
    "lovely words": 6,
    "just friends": 5,
    "take her hand": 7
}

manus_index = 0

# Load main controller

current_scene = 0
current_dialog = 0
manus = list(manus1)

def load_and_start(menu_frame):
    open_file()
    menu_frame.destroy()
    start_adventure(root)

def select_path(path, win):
    global manus, manus_index, current_scene, current_dialog, in_popup

    manus_index = choice_to_manus_index[path.strip().lower()]

    manus = list(manus_list[manus_index])
    current_scene = 0
    current_dialog = 0

    win.destroy()
    manus[current_scene].load(current_dialog)
    in_popup = False

def show_choice(paths):
    win, content = create_popup("Make a Choice", 420, 300)

    tk.Label(
        content,
        text="What will you do?",
        font=("Bell MT", 16, "bold"),
        fg="white",
        bg="#1c1c2e"
    ).pack(pady=10)

    for path in paths:
        btn = tk.Button(
            content,
            text=path,
            font=("Bell MT", 14),
            bg="#2e2e4f",
            fg="white",
            activebackground="#505080",
            relief="flat",
            width=25,
            command=lambda p=path: (select_path(p, win))
        )
        btn.pack(pady=5)

def next_dialog(event=None) -> None:
    if not active or in_popup:
        return
    global last_scene_time
    now = time.perf_counter()
    if now - last_scene_time < WAIT_TIME:
        return
    global current_dialog, current_scene, manus_index, manus
    last_scene_time = now
    current_dialog += 1
    if current_dialog >= len(manus[current_scene].dialogs):
        current_dialog = 0
        current_scene += 1
        if current_scene >= len(manus):
            current_scene = 0
            manus = manus_list[0]
            manus_index = 0
            load_menu(canvas)
            return
    scene = manus[current_scene]
    dialog = scene.dialogs[current_dialog]

    if dialog.choice is not None:
        show_choice(dialog.choice)
        return

    scene.load(current_dialog)

def start_adventure(root: tk.Tk) -> None:
    global binded, active
    manus[current_scene].load(current_dialog)
    if not binded:
        root.bind("<space>", next_dialog)
        root.bind("<Button-3>", next_dialog)
        root.bind("<Button-1>", next_dialog)
        root.bind("<Control-f>", set_scene)
        root.bind("<Control-o>", open_file)
        root.bind("<Control-s>", save_file)
        root.bind("<Control-m>", goto_menu)
        init_topbar(root)
        binded = True
    active = True

# Load menu

menu_frame = None

def load_menu(canvas: tk.Canvas) -> None:
    global active, manus, menu_frame
    active = False
    canvas.delete('all')
    menu_frame = tk.Frame(canvas, bg="black")
    canvas.create_window((0, 0), window=menu_frame, anchor="nw", height=height, width=width)

    manus = list(manus1)

    # --- LOGO ---
    try:
        logo_img = Image.open(THIS_PATH + ASSETS + "logo.png")  # add your own logo file
        logo_img = logo_img.resize((400, 150))
        logo_tk = ImageTk.PhotoImage(logo_img)

        logo_label = tk.Label(menu_frame, image=logo_tk, bg="black")
        logo_label.image = logo_tk  # prevent garbage collection
    except:
        # fallback if no logo image
        logo_label = tk.Label(
            menu_frame,
            text="Jack And Sophias' Romance",
            font=("Bell MT", 40),
            fg="white",
            bg="black"
        )

    logo_label.pack(pady=80)


    # --- START BUTTON ---
    start_button = tk.Button(
        menu_frame,
        text="Start",
        font=("Bell MT", 20),
        width=15,
        command=lambda: (menu_frame.destroy(), start_adventure(root))
    )
    start_button.pack(pady=10)

    # --- LOAD BUTTON ---
    load_button = tk.Button(
        menu_frame,
        text="Load",
        font=("Bell MT", 20),
        width=15,
        command=lambda: load_and_start(menu_frame)
    )
    load_button.pack(pady=10)

    # --- EXIT BUTTON ---
    exit_button = tk.Button(
        menu_frame,
        text="Exit",
        font=("Bell MT", 20),
        width=15,
        command=root.destroy
    )
    exit_button.pack(pady=10)

load_menu(canvas)

# Start mainloop
root.mainloop()