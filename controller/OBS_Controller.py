import argparse, base64, io, os, yaml
import dearpygui.dearpygui as dpg
import obsws_python as obs
from PIL import Image

# GUI Constants
RED = [255,0,0,255]
YELLOW = [255,255,0,255]
GREEN = [0,200,0,255]
TABLE_HEADER_COLOR = (38,72,125)
TABLE_HEIGHT = 100

def parse_commandline_args():
    parser = argparse.ArgumentParser(description="OBS Controller")
    parser.add_argument('-c','--config-file',help='The path to a configuration file.', required=False, type=str, default=r"config.yaml")
    args = parser.parse_args()
    
    if not os.path.exists(args.config_file):
        raise FileNotFoundError(f"Configuration file '{args.config_file}' not found. Make sure it exists and is spelled correctly.")

    print(f"Config from args: {args.config_file}")
    return args.config_file

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
    
try:
    cfg = load_config_yaml(parse_commandline_args())
except Exception as e:
    print("Failed to load config: ", e)
    exit()

obs_connections = cfg['obs_connections']
obs_active_clients = []
obs_client_previews = []
conn_failed = False
obs_active_conns = []
failed_conns = []

# Establish connections to OBS instances, track whether each connection was successful
for conn in obs_connections:
    try:
        client = obs.ReqClient(host=conn['host'], port=conn['port'], timeout=1)
        obs_active_clients.append(client)
        obs_active_conns.append(conn)
        print(f"Successfully connected to {conn['name']} at {conn['host']}:{conn['port']}")
    except Exception as e:
        failed_conns.append(conn)
        print(f"Failed to connect to {conn['name']} at {conn['host']}:{conn['port']}")
        conn_failed = True
        pass

if len(obs_active_clients) == 0:
    app_width = 450
else:
    app_width = (len(obs_active_clients) * 430) - ((len(obs_active_clients)-1) * 20)
app_height = 415
fail_modal_height = app_height - 150

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

# Get an initial screenshot for each connected OBS instance, useful for confirming it's recording the correct thing
for client in obs_active_clients:
    program_scene = client.get_current_program_scene()
    texture_data = decode_base64_to_image(client.get_source_screenshot(name=program_scene.current_program_scene_name, img_format='jpg', width=client.get_video_settings().base_width, height=client.get_video_settings().base_height, quality=10).image_data.replace('data:image/jpg;base64,', ''))
    obs_client_previews.append(texture_data)

with dpg.window(tag="Primary Window"):
    dpg.bind_font(default_font)

    # Notify user which connections failed, if any
    with dpg.window(label="Connections Failed", modal=True, show=conn_failed, tag="connection_fail", width=app_width-100, height=fail_modal_height, pos=(50,50)):
        dpg.add_text("The following failed to connect:")
        for conn in failed_conns:
            dpg.add_text(f" - {conn['name']} - {conn['host']}:{conn['port']}")
        dpg.add_text("Make sure the config file is correct\nand that OBS is open and configured.")
        dpg.add_spacer(height=50)
        dpg.add_button(label="Close", width=-1, height=50, callback=lambda: dpg.configure_item("connection_fail", show=False))

    with dpg.tab_bar():

        with dpg.tab(label="OBS"):
            with dpg.group(horizontal=True):
                for client in obs_active_clients:
                    conn = obs_active_conns[obs_active_clients.index(client)]

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
                                dpg.add_text("Error!", tag=f"recording_status_{conn}")
                                dpg.add_button(label="Toggle Recording", tag=f"toggle_recording_{conn}", width=-1, callback=obs_record_toggle_callback, user_data=client)
                            with dpg.table_row():
                                dpg.add_text("Error!", tag=f"recording_pause_status_{conn}")
                                dpg.add_button(label="Pause/Resume", tag=f"toggle_recording_pause_{conn}", width=-1, callback=obs_pause_toggle_callback, user_data=client)
                            with dpg.table_row():
                                dpg.add_text("Recording Length:")
                                dpg.add_text(label="00:00:00", tag=f"time_{conn}")
                        aspect_ratio = client.get_video_settings().base_height / client.get_video_settings().base_width
                        dpg.add_image(f"{conn}_preview", width=400, height=400 * aspect_ratio)
                        # dpg.add_image_button(f"{conn}_preview", width=392, height=392 * aspect_ratio, callback=update_screenshot_callback, user_data=client)

        with dpg.tab(label="BlackMagic"):
            with dpg.table(header_row=True, resizable=False, width=400, height=TABLE_HEIGHT, 
                           borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
                dpg.add_table_column(label="name")
                dpg.add_table_column(label=f'host:port')
                with dpg.table_row():
                    dpg.add_text(f"resolution")
                    dpg.add_text(f"fps")
                with dpg.table_row():
                    dpg.add_text("recording_status")
                    dpg.add_button(label="Toggle Recording", tag=f"toggle_recording_", width=-1)
                with dpg.table_row():
                    dpg.add_text("pause_status", tag=f"recording_pause_status_")
                    dpg.add_button(label="Pause/Resume", tag=f"toggle_recording_pause_", width=-1)
                with dpg.table_row():
                    dpg.add_text("Recording Length:")
                    dpg.add_text(label="00:00:00", tag=f"time_")

dpg.setup_dearpygui()
dpg.create_viewport(title=f"OBS Controller - 1 Connection" if len(obs_active_clients) == 1 else f"OBS Controller - {len(obs_active_clients)} Connections",
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
dpg.set_primary_window("Primary Window", True)

while dpg.is_dearpygui_running():
    dpg.set_viewport_title(f"OBS Controller - 1 Connection - {dpg.get_frame_rate()} fps" if len(obs_active_clients) == 1 else f"OBS Controller - {len(obs_active_clients)} Connections - {dpg.get_frame_rate()} fps")

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
        except Exception as e:
            # print(f"Error with {conn['name']}, {e}")
            dpg.set_value(f"fps_{conn}", "Error!")
            dpg.configure_item(f"fps_{conn}", color=RED)
            dpg.set_value(f"recording_status_{conn}", "Error!")
            dpg.configure_item(f"recording_status_{conn}", color=RED)
            dpg.set_value(f"recording_pause_status_{conn}", "Error!")
            dpg.configure_item(f"recording_pause_status_{conn}", color=RED)
            dpg.set_value(f"time_{conn}", "Error!")
            dpg.configure_item(f"time_{conn}", color=RED)
            pass

    dpg.render_dearpygui_frame()

dpg.destroy_context()
