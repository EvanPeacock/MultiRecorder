import argparse, base64, io, os, requests, time, yaml
import dearpygui.dearpygui as dpg
import obsws_python as obs
from PIL import Image

# GUI Constants
WHITE = [255,255,255,255]
RED = [255,0,0,255]
YELLOW = [255,255,0,255]
GREEN = [0,200,0,255]
TABLE_HEADER_COLOR = (38,72,125)
TABLE_HEIGHT = 100

# Command line args
parser = argparse.ArgumentParser(prog="MultiRecorder")
parser.add_argument('-c','--config-file',help='The path to a configuration file.', required=False, type=str, default=r"config.yaml")
parser.add_argument('-p','--show-previews',help='Whether the OBS connections should show an initial screenshot preview.', 
                    required=False, default=False, action='store_true')
parser.add_argument('-f','--show-fps',help='Whether the GUI should display frames per sseond in its title.', 
                    required=False, default=False, action='store_true')
parser.add_argument('-fps','--target-framerate',help='A target maximum framerate for the GUI.', required=False, type=int, default=60)
parser.add_argument('-d','--record-directory',help='Whether the GUI should show the record directory input.', 
                    required=False, default=False, action='store_true')
args = parser.parse_args()

# Timing Stuff
frame_frequency = 1/args.target_framerate
timing_t0 = time.perf_counter()
timing_counter = timing_t0

if not os.path.exists(args.config_file):
    raise FileNotFoundError(f"Configuration file '{args.config_file}' not found. Make sure it exists and is spelled correctly.")
else:
    print(f"Config from args: {args.config_file}")

show_previews = args.show_previews
print(f"Show Previews: {show_previews}")

show_fps = args.show_fps
print(f"Show FPS: {show_fps}")

record_directory = args.record_directory
print(f"Record Directory: {record_directory}")

def load_config_yaml(file_path):
    try:
        with open(file_path) as f:
            print(f"Successfully loaded {file_path}")
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None
    
# Decode base64 string to array that can be used in dearpygui
def decode_base64_to_image(base64_string):
    # Decode base64 string into bytes
    image_bytes = base64.b64decode(base64_string)

    # Create PIL Image object from bytes
    image = Image.open(io.BytesIO(image_bytes))

    # Convert PIL Image to list of tuples
    image_list = list(image.getdata())

    # Add alpha channel to image_list by appending 255 to each tuple
    alpha_image_list = [(r, g, b, 255) for r, g, b in image_list]

    # Flatten the list and convert the values to floats in the range 0-1
    image_list_1d = [float(i)/255 for sublist in alpha_image_list for i in sublist]

    return image_list_1d

# Currently doesn't work
def update_screenshot_callback(sender, app_data, user_data):
    program_scene = user_data.get_current_program_scene()
    texture_data = decode_base64_to_image(user_data.get_source_screenshot(name=program_scene.current_program_scene_name, img_format='jpg', width=user_data.get_video_settings().base_width, height=user_data.get_video_settings().base_height, quality=10).image_data.replace('data:image/jpg;base64,', ''))
    dpg.configure_item(f"{user_data.get_host()}_{user_data.get_port()}_preview", default_value=texture_data)
    
# Toggle recording for OBS connection
def obs_record_toggle_callback(sender, app_data, user_data):
    user_data.toggle_record()

# Pause/unpause recording for OBS connection
def obs_pause_toggle_callback(sender, app_data, user_data):
    user_data.toggle_record_pause()
    
# Toggle recording for BlackMagic connection
def bm_record_toggle_callback(sender, app_data, user_data):
    recording = requests.get(url=f"http://{user_data}/control/api/v1/transports/0/record").json().get('recording')
    requests.put(url=f"http://{user_data}/control/api/v1/transports/0/record", json={'recording': not recording})

# Start recording for all connections
def record_all_callback(sender, app_data, user_data):
    for client in obs_active_clients:
        status = client.get_record_status()
        is_recording = status.output_active
        if not is_recording:
            client.start_record()
    for conn in blackmagic_active_conns:
        recording = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording')
        if not recording:
            requests.put(url=f"http://{conn['host']}/control/api/v1/transports/0/record", json={'recording': True})

# Stop recording for all connections
def stop_all_callback(sender, app_data, user_data):
    for client in obs_active_clients:
        status = client.get_record_status()
        is_recording = status.output_active
        if is_recording:
            client.stop_record()
    for conn in blackmagic_active_conns:
        recording = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording')
        if recording:
            requests.put(url=f"http://{conn['host']}/control/api/v1/transports/0/record", json={'recording': False})

# Set the directory for recordings
def set_record_directory_callback(sender, app_data, user_data):
    success = True
    record_dir = dpg.get_value("record_dir")
    
    # Create directory for each OBS connection
    for client in obs_active_clients:
        conn = obs_active_conns[obs_active_clients.index(client)]
        directory_path = f"{record_dir}\\video\\{conn['name']}"
        try:
            if not os.path.exists(directory_path):
                os.makedirs(directory_path)
        except Exception as e:
            print(f"Failed to create directory: {e}")
            success = False
        client.set_record_directory(directory_path)

    # Set directory for each BlackMagic connection - Not yet sure if this is possible with current setup
    # for conn in blackmagic_active_conns:
    #     requests.put(url=f"http://{conn['host']}/control/api/v1/transports/0/clip", json={'clip': {'name': record_dir}})

    # Confirm directory was set
    if success:
        dpg.set_value("record_dir", "")
        dpg.configure_item("record_dir", hint=f"{record_dir}")

# Load config file
try:
    cfg = load_config_yaml(args.config_file)
except Exception as e:
    print("Failed to load config: ", e)
    exit()

# Track failed connections to notify user
conn_failed = False
failed_conns = []

# Establish connections to OBS instances, track whether each connection was successful
obs_connections = cfg['obs_connections']
if obs_connections is None or len(obs_connections) == 0:
    print("No OBS connections found in config.")
    obs_empty = True
else:
    obs_empty = False
obs_active_clients = []
obs_client_previews = []
obs_active_conns = []

if not obs_empty:
    for conn in obs_connections:
        try:
            # Check if host and port are the same as a previous connection
            if any(c['host'] == conn['host'] and c['port'] == conn['port'] for c in obs_active_conns):
                print(f"Duplicate OBS connections in config @ {conn['host']}:{conn['port']}, only one connection will be established.")
                continue
            
            client = obs.ReqClient(host=conn['host'], port=conn['port'], timeout=1)
            obs_active_clients.append(client)
            obs_active_conns.append(conn)
            print(f"Successfully connected to {conn['name']} @ {conn['host']}:{conn['port']}")
        except Exception as e:
            failed_conns.append(conn)
            print(f"Failed to connect to {conn['name']} @ {conn['host']}:{conn['port']}")
            conn_failed = True
            pass

    if obs_active_clients is None or len(obs_active_clients) == 0:
        print("All OBS connections failed.")
        obs_empty = True

# Establish connection to BlackMagic devices, track whether each connection was successful
blackmagic_connections = cfg['blackmagic_connections']
if blackmagic_connections is None or len(blackmagic_connections) == 0:
    print("No BlackMagic connections found in config.")
    blackmagic_empty = True
else:
    blackmagic_empty = False
blackmagic_client_previews = []
blackmagic_active_conns = []

if not blackmagic_empty:
    for conn in blackmagic_connections:
        try:
            # Check if host is the same as a previous connection
            if any(c['host'] == conn['host'] for c in blackmagic_active_conns):
                print(f"Duplicate BlackMagic connections in config @ {conn['host']}, only one connection will be established.")
                continue

            requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording')
            blackmagic_active_conns.append(conn)
            print(f"Successfully connected to {conn['name']} at {conn['host']}")
        except Exception as e:
            print(e)
            failed_conns.append(conn)
            print(f"Failed to connect to {conn['name']} at {conn['host']}")
            conn_failed = True
            pass

    if blackmagic_active_conns is None or len(blackmagic_active_conns) == 0:
        print("All BlackMagic connections failed.")
        blackmagic_empty = True

# Count the number of active connections and the number of connections currently recording
num_active_conns = len(obs_active_clients) + len(blackmagic_active_conns)
num_recording_conns = 0
for client in obs_active_clients:
    if client.get_record_status().output_active:
        num_recording_conns += 1
for conn in blackmagic_active_conns:
    if requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording'):
        num_recording_conns += 1

# Set up the GUI
if len(obs_active_clients) > len(blackmagic_active_conns):
    greatest_conns = len(obs_active_clients)
else:
    greatest_conns = len(blackmagic_active_conns)

if obs_empty and blackmagic_empty:
    app_width  = 500
    app_height = 500
else:
    if show_previews:
        app_width = (greatest_conns * 430) - ((greatest_conns-1) * 20)
        app_height = 480
    else:
        app_width = 430
        app_height = int(greatest_conns * TABLE_HEIGHT) + ((greatest_conns-1) * 8) + 150
fail_modal_height = app_height - 80
fail_modal_width = app_width - 80

dpg.create_context()
with dpg.font_registry():
    default_font = dpg.add_font(r"assets\B612Mono-Regular.ttf", 14)

# Theme - Taken from GCS Exec
with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 4,1, category=dpg.mvThemeCat_Core) # default is 4,2
        dpg.add_theme_color(dpg.mvThemeCol_TableHeaderBg,TABLE_HEADER_COLOR,category=dpg.mvThemeCat_Core)
    with dpg.theme_component(dpg.mvLineSeries):
        dpg.add_theme_style(dpg.mvPlotStyleVar_Marker,dpg.mvPlotMarker_Circle,category=dpg.mvThemeCat_Plots)
        dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize,1.5,category=dpg.mvThemeCat_Plots)
dpg.bind_theme(global_theme)

with dpg.theme() as tab_spacer:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Tab, [0,0,0,0], category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_TabHovered, [0,0,0,0], category=dpg.mvThemeCat_Core)

# Get an initial screenshot for each connected OBS instance, useful for confirming it's recording the correct thing
if show_previews and not obs_empty:
    for client in obs_active_clients:
        program_scene = client.get_current_program_scene()
        texture_data = decode_base64_to_image(client.get_source_screenshot(name=program_scene.current_program_scene_name, img_format='jpg', width=client.get_video_settings().base_width, height=client.get_video_settings().base_height, quality=10).image_data.replace('data:image/jpg;base64,', ''))
        obs_client_previews.append(texture_data)

with dpg.window(tag="Primary Window"):
    dpg.bind_font(default_font)

    # Notify user which connections failed, if any
    with dpg.window(label="Connections Failed", modal=True, show=conn_failed, tag="connection_fail",
                     width=fail_modal_width, height=fail_modal_height, pos=(30,20)):
        dpg.add_text("The following failed to connect:")
        for conn in failed_conns:
            if not obs_empty and conn in obs_connections:
                dpg.add_text(f" - {conn['name']} - {conn['host']}:{conn['port']}")
            else:
                dpg.add_text(f" - {conn['name']} - {conn['host']}")
        dpg.add_text("Make sure the config file is correct.")
        dpg.add_text("OBS: Make sure WebSocket is configured.")
        dpg.add_text("BlackMagic: Make sure remote is enabled.")
        dpg.add_text("BlackMagic: Check input is working.")
        # dpg.add_button(label="Close", width=-1, height=50, callback=lambda: dpg.configure_item("connection_fail", show=False))
    
    with dpg.tab_bar(tag="tab_bar", reorderable=True):

        if not obs_empty:
            with dpg.tab(label="OBS", order_mode=dpg.mvTabOrder_Reorderable):
                with dpg.group(horizontal=show_previews):
                    for client in obs_active_clients:
                        conn = obs_active_conns[obs_active_clients.index(client)]

                        if show_previews:
                            with dpg.texture_registry(show=False):
                                dpg.add_dynamic_texture(width=client.get_video_settings().base_width, height=client.get_video_settings().base_height, default_value=obs_client_previews[obs_active_clients.index(client)], tag=f"{conn}_preview", label=f"{conn}_preview")
                    
                        with dpg.group():
                            with dpg.table(header_row=True, resizable=False, width=400, height=TABLE_HEIGHT, 
                                            borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
                                dpg.add_table_column(label=conn['name'])
                                dpg.add_table_column(label=f'{conn["host"]}:{conn["port"]}')
                                with dpg.table_row():
                                    dpg.add_text(f"{client.get_video_settings().base_width}x{client.get_video_settings().base_height}")
                                    dpg.add_text(f"Error!", tag=f"fps_{conn}")
                                with dpg.table_row():
                                    dpg.add_text("Error!", tag=f"recording_pause_status_{conn}")
                                    dpg.add_button(label="Pause/Resume", tag=f"toggle_recording_pause_{conn}", width=-1, callback=obs_pause_toggle_callback, user_data=client)
                                with dpg.table_row():
                                    dpg.add_text("Error!", tag=f"recording_status_{conn}")
                                    dpg.add_button(label="Toggle Recording", tag=f"toggle_recording_{conn}", width=-1, callback=obs_record_toggle_callback, user_data=client)
                                with dpg.table_row():
                                    dpg.add_text("Recording Length:")
                                    dpg.add_text("00:00:00.000", tag=f"time_{conn}")
                            if show_previews:
                                aspect_ratio = client.get_video_settings().base_height / client.get_video_settings().base_width
                                dpg.add_image(f"{conn}_preview", width=400, height=400 * aspect_ratio)
                                # dpg.add_image_button(f"{conn}_preview", width=392, height=392 * aspect_ratio, callback=update_screenshot_callback, user_data=client)

        if not blackmagic_empty:
            with dpg.tab(label="BlackMagic", order_mode=dpg.mvTabOrder_Reorderable):
                for conn in blackmagic_active_conns:

                    with dpg.table(header_row=True, resizable=False, width=400, height=TABLE_HEIGHT, 
                                borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
                        dpg.add_table_column(label=conn['name'])
                        dpg.add_table_column(label=conn['host'])
                        with dpg.table_row():
                            clip = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/clip").json()
                            try:
                                dpg.add_text(f"{clip.get('clip').get('videoFormat').get('width')}x{clip.get('clip').get('videoFormat').get('height')}")
                            except Exception as e:
                                dpg.add_text("Error!")
                                print(f"Failed to get {conn['name']} resolution: {e}")
                                print(f"This is likely because the BlackMagic device isn't receiving any input.")

                            try:
                                dpg.add_text(f"{clip.get('clip').get('videoFormat').get('frameRate')}.0 FPS")
                            except Exception as e:
                                dpg.add_text("Error!")
                                print(f"Failed to get {conn['name']} framerate: {e}")
                                print(f"This is likely because the BlackMagic device isn't receiving any input.")

                        with dpg.table_row():
                            input_source = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/inputVideoSource").json()
                            try:
                                dpg.add_text(f"{input_source.get('inputVideoSource')}", tag=f"input_source_{conn}")
                            except Exception as e:
                                dpg.add_text("Error!")
                                print(f"Failed to get {conn['name']} input source: {e}")
                                print(f"This is likely because the BlackMagic device isn't receiving any input.")

                            try:
                                dpg.add_text(clip.get('clip').get('codecFormat').get('codec'), tag=f"codec_{conn}")
                            except Exception as e:
                                dpg.add_text("Error!")
                                print(f"Failed to get {conn['name']} codec: {e}")
                                print(f"This is likely because the BlackMagic device isn't receiving any input.")
                                
                        with dpg.table_row():
                            dpg.add_text("Error!", tag=f"recording_status_{conn}")
                            dpg.add_button(label="Toggle Recording", tag=f"toggle_recording_{conn}", width=-1,
                                        callback=bm_record_toggle_callback, user_data=conn['host'])
                        with dpg.table_row():
                            dpg.add_text("Recording Length:")
                            dpg.add_text("00:00:00", tag=f"time_{conn}")

        if not obs_empty and not blackmagic_empty:
            dpg.add_tab_button(label="           ", tag="tab_spacer")
        elif not obs_empty and blackmagic_empty:
            dpg.add_tab_button(label="                      ", tag="tab_spacer")
        elif obs_empty and not blackmagic_empty:
            dpg.add_tab_button(label="               ", tag="tab_spacer")
        else:
            dpg.add_tab_button(label="", tag="tab_spacer")
        dpg.bind_item_theme("tab_spacer", tab_spacer)
        dpg.add_tab_button(label="Record All", trailing=True, callback=record_all_callback)
        dpg.add_tab_button(label="Stop All",   trailing=True, callback=stop_all_callback)

    with dpg.tree_node(label="Status & Settings", default_open=True):
        if num_active_conns == 1:
            dpg.add_text(f"{num_active_conns} connection, {num_recording_conns} recording", tag="connection_status", show=not conn_failed)
        else:
            dpg.add_text(f"{num_active_conns} connections, {num_recording_conns} recording", tag="connection_status", show=not conn_failed)

        dpg.add_slider_int(label="GUI Target Framerate", width=196, default_value=args.target_framerate, min_value=10, max_value=60, tag="target_framerate")

        if record_directory:
            with dpg.table(header_row=False, resizable=False, width=-1, height=10, borders_innerH=False, borders_outerH=False, borders_innerV=False, borders_outerV=False):
                dpg.add_table_column()
                dpg.add_table_column()
                with dpg.table_row():
                    dpg.add_input_text(hint="Record Directory", width=-1, tag="record_dir")
                    dpg.add_button(label="Enter", width=-1, callback=set_record_directory_callback)

dpg.setup_dearpygui()
dpg.create_viewport(title="MultiRecorder",
    width=app_width,
    height=app_height,
    vsync=False,
    resizable=False,
    small_icon = r"assets\icon.ico",
    large_icon = r"assets\icon.ico",
    max_height=app_width + 50,
    max_width=app_height + 50,
    min_width=app_width,
    min_height=app_height,)

dpg.show_viewport()
# dpg.show_style_editor()
dpg.set_primary_window("Primary Window", True)

while dpg.is_dearpygui_running():
    if show_fps:
        dpg.set_viewport_title(title=f"MultiRecorder - {dpg.get_frame_rate()} fps")

    if not obs_empty:
        for client in obs_active_clients:
            conn = obs_active_conns[obs_active_clients.index(client)]
            try:
                status = client.get_record_status()
                is_recording = status.output_active
                is_paused = client.get_record_status().output_paused

                dpg.set_value(f"fps_{conn}", f"{client.get_video_settings().fps_numerator / client.get_video_settings().fps_denominator} FPS")

                if is_recording:
                    dpg.set_value(f"recording_status_{conn}", "Recording")
                    dpg.configure_item(f"recording_status_{conn}", color=GREEN)
                    if is_paused:
                        dpg.set_value(f"recording_pause_status_{conn}", "Paused")
                        dpg.configure_item(f"recording_pause_status_{conn}", color=YELLOW)
                    else:
                        dpg.set_value(f"recording_pause_status_{conn}", "Not Paused")
                        dpg.configure_item(f"recording_pause_status_{conn}", color=GREEN)
                        dpg.set_value(f"time_{conn}", f"{status.output_timecode}")
                else:
                    dpg.set_value(f"recording_status_{conn}", "Not Recording")
                    dpg.configure_item(f"recording_status_{conn}", color=RED)
                    dpg.set_value(f"recording_pause_status_{conn}", "Not Recording")
                    dpg.configure_item(f"recording_pause_status_{conn}", color=RED)

                dpg.configure_item(f"fps_{conn}", color=WHITE)
                dpg.configure_item(f"time_{conn}", color=WHITE)
            except Exception as e:
                dpg.set_value(f"time_{conn}", "Error!")
                dpg.configure_item(f"time_{conn}", color=RED)
                pass
    
    if not blackmagic_empty:
        for conn in blackmagic_active_conns:
            try:
                recording = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording')
                if recording:
                    dpg.set_value(f"recording_status_{conn}", "Recording")
                    dpg.configure_item(f"recording_status_{conn}", color=GREEN)
                    timecode = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/timecode").json().get('display')
                else:
                    dpg.set_value(f"recording_status_{conn}", "Not Recording")
                    dpg.configure_item(f"recording_status_{conn}", color=RED)
                    timecode = requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/timecode").json().get('timeline')
                dpg.set_value(f"time_{conn}", timecode)

                dpg.configure_item(f"time_{conn}", color=WHITE)
            except Exception as e:
                dpg.set_value(f"time_{conn}", "Error!")
                dpg.configure_item(f"time_{conn}", color=RED)
                pass

    # Update number of connections currently recording
    try:
        new_num_recording_conns = 0
        for client in obs_active_clients:
            if client.get_record_status().output_active:
                new_num_recording_conns += 1
        for conn in blackmagic_active_conns:
            if requests.get(url=f"http://{conn['host']}/control/api/v1/transports/0/record").json().get('recording'):
                new_num_recording_conns += 1
        if new_num_recording_conns != num_recording_conns:
            num_recording_conns = new_num_recording_conns
            if num_active_conns == 1:
                dpg.set_value("connection_status", f"{num_active_conns} connection, {num_recording_conns} recording")
            else:
                dpg.set_value("connection_status", f"{num_active_conns} connections, {num_recording_conns} recording")
    except Exception as e:
        print(f"Failed to update recording count: {e}")
        pass

    # Cap at target fps
    frame_frequency = 1/dpg.get_value("target_framerate")
    now = time.perf_counter()
    elapsed_time = now - timing_counter
    if elapsed_time < frame_frequency:
        target_time =  frame_frequency - elapsed_time
        time.sleep(target_time)
    timing_counter += frame_frequency

    dpg.render_dearpygui_frame()

dpg.destroy_context()
