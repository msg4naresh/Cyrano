import mss
import io
import base64
import tkinter as tk
from PIL import Image


def capture_screen() -> str:
    """
    Captures full screen (main monitor).
    Returns base64-encoded PNG string ready for Claude Vision API.
    """
    with mss.mss() as sct:
        # monitors[0] = all monitors combined
        # monitors[1] = main monitor only
        screenshot = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode()


def capture_selection(root: tk.Tk) -> str | None:
    """
    Opens a fullscreen transparent overlay for user to drag-select a region.
    Returns base64-encoded PNG of the selected region, or None if cancelled.
    """
    selection = {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "done": False, "cancelled": False}
    
    # Create fullscreen selection window
    sel_win = tk.Toplevel(root)
    sel_win.attributes("-fullscreen", True)
    sel_win.attributes("-alpha", 0.3)
    sel_win.attributes("-topmost", True)
    sel_win.configure(bg="black")
    sel_win.config(cursor="crosshair")
    
    canvas = tk.Canvas(sel_win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    rect_id = None
    
    def on_press(event):
        nonlocal rect_id
        selection["x1"] = event.x_root
        selection["y1"] = event.y_root
        if rect_id:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#58d68d", width=2
        )
    
    def on_drag(event):
        nonlocal rect_id
        if rect_id:
            canvas.coords(rect_id, 
                selection["x1"] - sel_win.winfo_rootx(),
                selection["y1"] - sel_win.winfo_rooty(),
                event.x, event.y)
    
    def on_release(event):
        selection["x2"] = event.x_root
        selection["y2"] = event.y_root
        selection["done"] = True
        sel_win.destroy()
    
    def on_escape(event):
        selection["cancelled"] = True
        sel_win.destroy()
    
    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    sel_win.bind("<Escape>", on_escape)
    
    # Wait for selection to complete
    sel_win.grab_set()
    root.wait_window(sel_win)
    
    if selection["cancelled"] or not selection["done"]:
        return None
    
    # Normalize coordinates (handle any drag direction)
    x1 = min(selection["x1"], selection["x2"])
    y1 = min(selection["y1"], selection["y2"])
    x2 = max(selection["x1"], selection["x2"])
    y2 = max(selection["y1"], selection["y2"])
    
    width = x2 - x1
    height = y2 - y1
    
    if width < 10 or height < 10:
        return None  # Too small
    
    # Capture the selected region
    with mss.mss() as sct:
        region = {"left": x1, "top": y1, "width": width, "height": height}
        screenshot = sct.grab(region)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode()
