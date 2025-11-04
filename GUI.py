import tkinter as tk
import socket
import threading
import time

#Global Variables
cybot_file = None
app_running = True

#Called by connect button, it starts main network function in new thread
def start_listener_thread():
    t = threading.Thread(target=connect_and_listen, daemon=True)
    t.start()


#Runs in background thread, sends m and then listens for data
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
        cybot_file.write("m\n".encode())

        #Main listening loop
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
                print(f"Could not parse data")
    except Exception as e:
        status_var.set(f"{e}")
    finally:
        if cybot_file:
            cybot_file.close()
        status_var.set("Disconnected")

#Called when X is clicked
def on_closing():
    global app_running
    app_running = False

    time.sleep(0.1)

    window.destroy()


#Setup for main window
window = tk.Tk()
window.title("PING Sensor Dashboard")
window.geometry("400x350")

#StringVars to hold the dynamic data being sent
dist_var = tk.StringVar(value="-- cm")
cycle_var = tk.StringVar(value="-- ticks")
overflow_var = tk.StringVar(value="-- overflows")
status_var = tk.StringVar(value="Not Connected")

#Connection details
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

connect_button = tk.Button(window, text="Connect & Start Scan", command=start_listener_thread)
connect_button.pack(pady=10)

status_label = tk.Label(window, textvariable=status_var)
status_label.pack(pady=5)

#Displaying data
tk.Label(window, text="Distance:", font=("Helvetica", 14)).pack(pady=(20, 0))
tk.Label(window, textvariable=dist_var, font=("Helvetica", 12,)).pack()

tk.Label(window, text="Pulse Width:", font=("Helvetica", 14)).pack(pady=(10, 0))
tk.Label(window, textvariable=cycle_var, font=("Helvetica", 12,)).pack()

tk.Label(window, text="Overflows:", font=("Helvetica", 14)).pack(pady=(20, 0))
tk.Label(window, textvariable=overflow_var, font=("Helvetica", 12,)).pack()

window.protocol("WM_DELETE_WINDOW", on_closing)
window.mainloop()