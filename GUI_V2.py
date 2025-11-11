import tkinter as tk
import socket
import threading
import time

# Global Variables
cybot_file = None
app_running = True


#Function to send any command to the Cybot
def send_command(command):
    global cybot_file
    if cybot_file:
        try:
            # Send the command character
            cybot_file.write(f"{command}\n".encode())
            status_var.set(f"Sent command: {command}")
        except Exception as e:
            status_var.set(f"Error sending: {e}")
    else:
        status_var.set("Not connected. Press 'Connect' first.")


#Handler for keypress events
def on_key_press(event):
    command = event.char
    if command in ['w', 'a', 's', 'd', 'm']:
        send_command(command)
    elif command == ' ':
        send_command(' ')  # Assuming spacebar is a 'stop' command


# Called by connect button, it starts main network function in new thread
def start_listener_thread():
    t = threading.Thread(target=connect_and_listen, daemon=True)
    t.start()


def connect_and_listen():
    global cybot_file, app_running

    try:
        HOST = host_entry.get()
        PORT = int(port_entry.get())

        status_var.set(f"Connecting to {HOST}:{PORT}")
        cybot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cybot_socket.connect((HOST, PORT))

        cybot_file = cybot_socket.makefile("rbw", buffering=1)
        status_var.set("Connected")

        # Main listening loop
        while app_running:
            rx_message_bytes = cybot_file.readline()

            if not rx_message_bytes:
                raise Exception("Disconnected")

            rx_message_bytes = rx_message_bytes.decode('utf-8').strip()

            try:
                parts = rx_message_bytes.split(',')
                if len(parts) == 3:
                    dist_var.set(f"{parts[0]} cm")
                    cycle_var.set(f"{parts[1]} ticks")
                    overflow_var.set(f"{parts[2]} overflows")
            except Exception as e:
                print(f"Could not parse data: {rx_message_bytes}")
    except Exception as e:
        status_var.set(f"{e}")
    finally:
        if cybot_file:
            cybot_file.close()
        status_var.set("Disconnected")


# Called when X is clicked
def on_closing():
    global app_running
    app_running = False

    time.sleep(0.1)

    window.destroy()


# Setup for main window
window = tk.Tk()
window.title("CyBot Control & PING Sensor")
window.geometry("400x500")

# StringVars to hold the dynamic data being sent
dist_var = tk.StringVar(value="-- cm")
cycle_var = tk.StringVar(value="-- ticks")
overflow_var = tk.StringVar(value="-- overflows")
status_var = tk.StringVar(value="Not Connected")

# Connection details
conn_frame = tk.Frame(window)

tk.Label(conn_frame, text="Host:").pack(side=tk.LEFT, padx=5)
host_entry = tk.Entry(conn_frame)
host_entry.insert(0, "192.168.1.1")
host_entry.pack(side=tk.LEFT)

tk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
port_entry = tk.Entry(conn_frame)
port_entry.insert(0, "288")
port_entry.pack(side=tk.LEFT)
conn_frame.pack(pady=5)


connect_button = tk.Button(window, text="Connect", command=start_listener_thread)
connect_button.pack(pady=5)

scan_button = tk.Button(window, text="Scan (m)", command=lambda: send_command('m'))
scan_button.pack(pady=5)

status_label = tk.Label(window, textvariable=status_var)
status_label.pack(pady=5)

move_frame = tk.Frame(window)
move_frame.pack(pady=10)

tk.Label(move_frame, text="Movement Controls", font=("Helvetica", 14)).grid(row=0, column=0, columnspan=3, pady=5)

fwd_button = tk.Button(move_frame, text="Forward (w)", command=lambda: send_command('w'))
fwd_button.grid(row=1, column=1)

left_button = tk.Button(move_frame, text="Left (a)", command=lambda: send_command('a'))
left_button.grid(row=2, column=0, padx=5)

back_button = tk.Button(move_frame, text="Backward (s)", command=lambda: send_command('s'))
back_button.grid(row=2, column=1)

right_button = tk.Button(move_frame, text="Right (d)", command=lambda: send_command('d'))
right_button.grid(row=2, column=2, padx=5)


data_frame = tk.Frame(window)
data_frame.pack(pady=10)

tk.Label(data_frame, text="Distance:", font=("Helvetica", 14)).pack(pady=(10, 0))
tk.Label(data_frame, textvariable=dist_var, font=("Helvetica", 12,)).pack()

tk.Label(data_frame, text="Pulse Width:", font=("Helvetica", 14)).pack(pady=(10, 0))
tk.Label(data_frame, textvariable=cycle_var, font=("Helvetica", 12,)).pack()

tk.Label(data_frame, text="Overflows:", font=("Helvetica", 14)).pack(pady=(10, 0))
tk.Label(data_frame, textvariable=overflow_var, font=("Helvetica", 12,)).pack()

#Bind keypresses to the main window
window.bind("<Key>", on_key_press)

window.protocol("WM_DELETE_WINDOW", on_closing)
window.mainloop()
