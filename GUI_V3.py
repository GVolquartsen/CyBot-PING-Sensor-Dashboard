import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import threading
import math
import time
import queue

# --- CONFIGURATION ---
CYBOT_IP = "192.168.1.1"  
CYBOT_PORT = 288          
# ---------------------

class CyBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CyBot Mission Control")
        self.root.geometry("1000x700")
        self.root.configure(bg="#2c3e50")

        # --- Data State ---
        self.connected = False
        self.socket = None
        self.msg_queue = queue.Queue()
        
        # Robot State (Dead Reckoning)
        # Start at (0,0) facing 90 degrees (UP)
        self.bot_x = 0.0
        self.bot_y = 0.0 
        self.bot_heading = 90.0 
        self.path = [(0, 0)]
        self.objects = [] # List of (x, y) tuples

        # Scale: Pixels per CM
        self.scale = 2.0 
        self.grid_size = 50 # cm

        self.setup_ui()
        
        # Start GUI Update Loop
        self.root.after(100, self.process_queue)

        # Start Connection Thread
        self.log("System", "Initializing network thread...")
        self.net_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.net_thread.start()

    def setup_ui(self):
        # --- Layout ---
        # Left: Canvas (Map)
        # Right: Controls & Logs
        
        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel
        self.canvas_frame = tk.Frame(main_frame, bg="black", bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.draw_map) # Redraw on resize

        # Overlay Info on Canvas
        self.info_label = tk.Label(self.canvas_frame, text="X: 0 Y: 0 H: 90", 
                                 bg="#1a1a1a", fg="#00ff00", font=("Consolas", 10), anchor="w")
        self.info_label.place(x=10, y=10)

        # Right Panel
        right_panel = tk.Frame(main_frame, width=300, bg="#34495e")
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False) # Force width

        # Status Header
        self.status_lbl = tk.Label(right_panel, text="DISCONNECTED", bg="#c0392b", fg="white", 
                                 font=("Arial", 12, "bold"), pady=10)
        self.status_lbl.pack(fill=tk.X)

        # Approval Section
        approval_frame = tk.LabelFrame(right_panel, text="Approvals", bg="#34495e", fg="white", pady=10)
        approval_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.req_label = tk.Label(approval_frame, text="No pending requests.", 
                                bg="#34495e", fg="#bdc3c7", wraplength=280)
        self.req_label.pack(pady=5)

        btn_frame = tk.Frame(approval_frame, bg="#34495e")
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.btn_yes = tk.Button(btn_frame, text="APPROVE (Y)", bg="#27ae60", fg="white", 
                               state=tk.DISABLED, command=lambda: self.send_response('y'))
        self.btn_yes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.btn_no = tk.Button(btn_frame, text="DENY (N)", bg="#c0392b", fg="white", 
                              state=tk.DISABLED, command=lambda: self.send_response('n'))
        self.btn_no.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Manual Control
        control_frame = tk.LabelFrame(right_panel, text="Manual Control", bg="#34495e", fg="white")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctrl_grid = tk.Frame(control_frame, bg="#34495e")
        ctrl_grid.pack(pady=5)
        
        tk.Button(ctrl_grid, text="▲", command=lambda: self.send_command('w'), width=5).grid(row=0, column=1)
        tk.Button(ctrl_grid, text="◄", command=lambda: self.send_command('a'), width=5).grid(row=1, column=0)
        tk.Button(ctrl_grid, text="▼", command=lambda: self.send_command('s'), width=5).grid(row=1, column=1)
        tk.Button(ctrl_grid, text="►", command=lambda: self.send_command('d'), width=5).grid(row=1, column=2)
        
        # Keyboard bindings
        self.root.bind('<w>', lambda e: self.send_command('w'))
        self.root.bind('<a>', lambda e: self.send_command('a'))
        self.root.bind('<s>', lambda e: self.send_command('s'))
        self.root.bind('<d>', lambda e: self.send_command('d'))

        # Logs
        log_frame = tk.LabelFrame(right_panel, text="Telemetry Log", bg="#34495e", fg="white")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, bg="#2c3e50", fg="#ecf0f1", 
                                                font=("Consolas", 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)

    # --- Network Logic (Runs in Thread) ---
    def network_loop(self):
        while True:
            try:
                self.msg_queue.put(("STATUS", "CONNECTING..."))
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5)
                self.socket.connect((CYBOT_IP, CYBOT_PORT))
                
                self.msg_queue.put(("STATUS", "CONNECTED"))
                self.connected = True
                
                while True:
                    data = self.socket.recv(1024)
                    if not data: break
                    text = data.decode('utf-8', errors='ignore').strip()
                    # Handle multiple messages in one packet
                    for line in text.split('\n'):
                        if line:
                            self.msg_queue.put(("DATA", line.strip()))
                            
            except Exception as e:
                self.msg_queue.put(("LOG", f"Connection Error: {e}"))
                self.msg_queue.put(("STATUS", "DISCONNECTED"))
                self.connected = False
                time.sleep(3) # Retry delay

    def send_command(self, char):
        if self.connected and self.socket:
            try:
                self.socket.sendall(char.encode('utf-8'))
                self.log("CMD", f"Sent: {char}")
            except:
                self.log("Error", "Failed to send command")

    def send_response(self, char):
        self.send_command(char)
        # Reset UI
        self.req_label.config(text="No pending requests.", fg="#bdc3c7")
        self.btn_yes.config(state=tk.DISABLED)
        self.btn_no.config(state=tk.DISABLED)

    # --- Main GUI Loop (Updates UI from Queue) ---
    def process_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                
                if msg_type == "STATUS":
                    color = "#27ae60" if content == "CONNECTED" else "#c0392b"
                    self.status_lbl.config(text=content, bg=color)
                
                elif msg_type == "LOG":
                    self.log("Sys", content)
                    
                elif msg_type == "DATA":
                    self.parse_telemetry(content)
                    
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self.process_queue)

    # --- Telemetry Parsing & Physics ---
    def parse_telemetry(self, raw_str):
        self.log("RX", raw_str)
        try:
            parts = raw_str.split(',')
            cmd = parts[0]

            if cmd == "MOV":
                dist = float(parts[1])
                self.update_position(dist, 0)
            
            elif cmd == "TURN":
                angle = float(parts[1])
                self.update_position(0, angle)
                
            elif cmd == "OBJ":
                # OBJ, angle, distance
                scan_angle = float(parts[1])
                dist = float(parts[2])
                self.add_object(scan_angle, dist)
                
            elif cmd == "REQ":
                # REQ, message
                message = parts[1] if len(parts) > 1 else "Action required?"
                self.req_label.config(text=message, fg="#f1c40f")
                self.btn_yes.config(state=tk.NORMAL)
                self.btn_no.config(state=tk.NORMAL)
                # Play alert sound
                self.root.bell()

        except Exception as e:
            print(f"Parse error: {e}")

    def update_position(self, move_dist, turn_angle):
        # Update Heading
        self.bot_heading += turn_angle
        
        # Calculate new X, Y based on Heading
        # Math: 0 deg is East, but our Bot 90 is North. 
        # Standard Trig: x = cos(theta), y = sin(theta)
        # Convert degrees to radians
        rad = math.radians(self.bot_heading)
        
        dx = math.cos(rad) * move_dist
        dy = math.sin(rad) * move_dist
        
        self.bot_x += dx
        self.bot_y += dy
        
        self.path.append((self.bot_x, self.bot_y))
        self.draw_map()

    def add_object(self, scan_angle, dist):
        # Calculate absolute angle of object
        # Object Angle relative to map = Bot Heading + Scan Angle
        abs_angle_rad = math.radians(self.bot_heading + scan_angle)
        
        obj_x = self.bot_x + (math.cos(abs_angle_rad) * dist)
        obj_y = self.bot_y + (math.sin(abs_angle_rad) * dist)
        
        self.objects.append((obj_x, obj_y))
        self.draw_map()

    # --- Drawing Engine ---
    def draw_map(self, event=None):
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w/2, h/2 # Center of canvas
        
        # Coordinate Transform Function (World -> Screen)
        def to_screen(x, y):
            # Scale and Flip Y (Canvas Y is down, World Y is up)
            return cx + (x * self.scale), cy - (y * self.scale)

        # 1. Draw Grid
        self.canvas.create_line(cx, 0, cx, h, fill="#34495e", dash=(2, 4)) # Y Axis
        self.canvas.create_line(0, cy, w, cy, fill="#34495e", dash=(2, 4)) # X Axis
        
        # 2. Draw Path
        if len(self.path) > 1:
            screen_coords = [to_screen(x, y) for x, y in self.path]
            # Flatten list for create_line
            flat_coords = [val for pair in screen_coords for val in pair]
            self.canvas.create_line(flat_coords, fill="#27ae60", width=2)

        # 3. Draw Objects
        for ox, oy in self.objects:
            sx, sy = to_screen(ox, oy)
            self.canvas.create_oval(sx-2, sy-2, sx+2, sy+2, fill="#c0392b", outline="")

        # 4. Draw Robot
        bx, by = to_screen(self.bot_x, self.bot_y)
        # Robot is a triangle pointing in heading direction
        head_rad = math.radians(self.bot_heading)
        
        # Nose
        nx = bx + math.cos(head_rad) * 10
        ny = by - math.sin(head_rad) * 10 # Y flip for screen math
        
        # Back Left
        blx = bx + math.cos(head_rad + 2.5) * 8
        bly = by - math.sin(head_rad + 2.5) * 8
        
        # Back Right
        brx = bx + math.cos(head_rad - 2.5) * 8
        bry = by - math.sin(head_rad - 2.5) * 8
        
        self.canvas.create_polygon(nx, ny, blx, bly, brx, bry, fill="#3498db", outline="white")
        
        # Update Label
        self.info_label.config(text=f"X: {self.bot_x:.1f}  Y: {self.bot_y:.1f}  H: {self.bot_heading:.0f}°")

    def log(self, tag, msg):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, f"[{tag}] {msg}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = CyBotGUI(root)
    root.mainloop()
