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
        self.bot_x = 0.0
        self.bot_y = 0.0 
        self.bot_heading = 90.0 
        self.path = [(0, 0)]
        self.objects = [] 

        # Bounding Box for Dynamic Scaling (Min/Max values in CM)
        # Initializes a reasonable viewing window (1m x 1m)
        self.min_x = -50.0
        self.max_x = 50.0
        self.min_y = -50.0
        self.max_y = 50.0
        
        # Dynamic Scaling variables
        self.scale = 2.0 
        self.grid_cm = 50 # Grid line every 50cm

        self.setup_ui()
        
        self.log("System", "Initializing network thread...")
        self.net_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.net_thread.start()
        
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#2c3e50")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel (Map)
        self.canvas_frame = tk.Frame(main_frame, bg="black", bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.draw_map) 

        # Overlay Info on Canvas
        self.info_label = tk.Label(self.canvas_frame, text="X: 0 Y: 0 H: 90", 
                                 bg="#1a1a1a", fg="#00ff00", font=("Consolas", 10), anchor="w")
        self.info_label.place(x=10, y=10)

        # Right Panel (Controls & Logs)
        right_panel = tk.Frame(main_frame, width=300, bg="#34495e")
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False) 

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
        self.root.bind('<m>', lambda e: self.send_command('m')) 

        # Logs
        log_frame = tk.LabelFrame(right_panel, text="Telemetry Log", bg="#34495e", fg="white")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, bg="#2c3e50", fg="#ecf0f1", 
                                                font=("Consolas", 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
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
                    for line in text.split('\n'):
                        if line:
                            self.msg_queue.put(("DATA", line.strip()))
                            
            except Exception as e:
                self.msg_queue.put(("LOG", f"Connection Error: {e}"))
                self.msg_queue.put(("STATUS", "DISCONNECTED"))
                self.connected = False
                time.sleep(3) 

    def send_command(self, char):
        if self.connected and self.socket:
            try:
                self.socket.sendall(char.encode('utf-8'))
                self.log("CMD", f"Sent: {char}")
            except:
                self.log("Error", "Failed to send command")

    def send_response(self, char):
        self.send_command(char)
        self.req_label.config(text="No pending requests.", fg="#bdc3c7")
        self.btn_yes.config(state=tk.DISABLED)
        self.btn_no.config(state=tk.DISABLED)

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

    def parse_telemetry(self, raw_str):
        self.log("RX", raw_str)
        try:
            parts = raw_str.split(',')
            cmd = parts[0]

            if cmd == "MOV":
                dist = float(parts[1])
                self.update_position(dist, 0)
            
            elif cmd == "TURN":
                # Now correctly parses the float (e.g., -48.60)
                angle = float(parts[1]) 
                self.update_position(0, angle)
                
            elif cmd == "OBJ":
                scan_angle = float(parts[1])
                dist = float(parts[2])
                self.add_object(scan_angle, dist)
                
            elif cmd == "REQ":
                message = parts[1] if len(parts) > 1 else "Action required?"
                self.req_label.config(text=message, fg="#f1c40f")
                self.btn_yes.config(state=tk.NORMAL)
                self.btn_no.config(state=tk.NORMAL)
                self.root.bell()

        except Exception as e:
            self.log("Parse Error", f"{e} in data: {raw_str}")

    def update_position(self, move_dist, turn_angle):
        
        # 1. Update Heading
        self.bot_heading = (self.bot_heading + turn_angle) % 360
        
        # 2. Update Position
        rad = math.radians(self.bot_heading)
        
        dx = math.cos(rad) * move_dist
        dy = math.sin(rad) * move_dist
        
        self.bot_x += dx
        self.bot_y += dy
        
        self.path.append((self.bot_x, self.bot_y))

        # 3. Update Bounding Box for dynamic map
        self.min_x = min(self.min_x, self.bot_x)
        self.max_x = max(self.max_x, self.bot_x)
        self.min_y = min(self.min_y, self.bot_y)
        self.max_y = max(self.max_y, self.bot_y)
        
        self.draw_map()

    def add_object(self, scan_angle, dist):
        # Calculate absolute angle of object
        abs_angle_rad = math.radians(self.bot_heading + scan_angle)
        
        obj_x = self.bot_x + (math.cos(abs_angle_rad) * dist)
        obj_y = self.bot_y + (math.sin(abs_angle_rad) * dist)
        
        self.objects.append((obj_x, obj_y))
        
        # Update Bounding Box for objects too
        self.min_x = min(self.min_x, obj_x)
        self.max_x = max(self.max_x, obj_x)
        self.min_y = min(self.min_y, obj_y)
        self.max_y = max(self.max_y, obj_y)
        
        self.draw_map()

    # --- Drawing Engine (Dynamic) ---
    def draw_map(self, event=None):
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # 1. Determine Dynamic Scale
        map_width_cm = max(abs(self.max_x - self.min_x), 100) 
        map_height_cm = max(abs(self.max_y - self.min_y), 100)
        
        padding_factor = 1.2
        
        scale_x = w / (map_width_cm * padding_factor)
        scale_y = h / (map_height_cm * padding_factor)
        
        self.scale = min(scale_x, scale_y) 
        
        # Calculate translation offsets to center the map
        center_x_cm = (self.min_x + self.max_x) / 2
        center_y_cm = (self.min_y + self.max_y) / 2
        
        translate_x = w / 2 - center_x_cm * self.scale
        translate_y = h / 2 + center_y_cm * self.scale 

        # Coordinate Transform Function (World -> Screen)
        def to_screen(x, y):
            # Scale, invert Y, and apply translation
            sx = x * self.scale + translate_x
            sy = h - (y * self.scale + (h - translate_y)) 
            return sx, sy

        # 2. Draw Dynamic Grid
        self.canvas.create_rectangle(0, 0, w, h, fill="#1a1a1a") 

        # Draw vertical grid lines
        start_cm_x = self.min_x - (self.min_x % self.grid_cm) - self.grid_cm
        end_cm_x = self.max_x + self.grid_cm
        for x_cm in range(int(start_cm_x), int(end_cm_x), self.grid_cm):
            sx, _ = to_screen(x_cm, 0)
            self.canvas.create_line(sx, 0, sx, h, fill="#34495e", dash=(2, 4))
            self.canvas.create_text(sx, h - 10, text=f"{x_cm}cm", fill="#607d8b", anchor="s")

        # Draw horizontal grid lines
        start_cm_y = self.min_y - (self.min_y % self.grid_cm) - self.grid_cm
        end_cm_y = self.max_y + self.grid_cm
        for y_cm in range(int(start_cm_y), int(end_cm_y), self.grid_cm):
            _, sy = to_screen(0, y_cm)
            self.canvas.create_line(0, sy, w, sy, fill="#34495e", dash=(2, 4))
            self.canvas.create_text(10, sy + 5, text=f"{y_cm}cm", fill="#607d8b", anchor="w")
            
        # 3. Draw Path
        if len(self.path) > 1:
            screen_coords = [to_screen(x, y) for x, y in self.path]
            flat_coords = [val for pair in screen_coords for val in pair]
            self.canvas.create_line(flat_coords, fill="#27ae60", width=2)

        # 4. Draw Objects
        for ox, oy in self.objects:
            sx, sy = to_screen(ox, oy)
            self.canvas.create_oval(sx-4, sy-4, sx+4, sy+4, fill="#c0392b", outline="")

        # 5. Draw Robot
        bx, by = to_screen(self.bot_x, self.bot_y)
        
        # Robot Body (Triangle)
        head_rad = math.radians(self.bot_heading)
        tri_size = 10 
        
        nx = bx + math.cos(head_rad) * tri_size
        ny = by - math.sin(head_rad) * tri_size 
        
        blx = bx + math.cos(head_rad + 2.5) * tri_size * 0.8
        bly = by - math.sin(head_rad + 2.5) * tri_size * 0.8
        
        brx = bx + math.cos(head_rad - 2.5) * tri_size * 0.8
        bry = by - math.sin(head_rad - 2.5) * tri_size * 0.8
        
        self.canvas.create_polygon(nx, ny, blx, bly, brx, bry, fill="#3498db", outline="white")
        
        # Update Label
        self.info_label.config(text=f"X: {self.bot_x:.1f} cm  Y: {self.bot_y:.1f} cm  H: {self.bot_heading:.1f}°")

    def log(self, tag, msg):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, f"[{tag}] {msg}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = CyBotGUI(root)
    root.mainloop()
