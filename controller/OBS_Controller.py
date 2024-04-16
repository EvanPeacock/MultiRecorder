import argparse, os, yaml
import dearpygui.dearpygui as dpg
import obsws_python as obs

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
    
try:
    cfg = load_config_yaml(parse_commandline_args())
except Exception as e:
    print(e)
    exit()
connections = cfg['connections']
active_clients = []
active_conns = []
conn_failed = False
failed_conns = []

for conn in connections:
    try:
        client = obs.ReqClient(host=conn['host'], port=conn['port'], timeout=1)
        active_clients.append(client)
        active_conns.append(conn)
        print(f"Successfully connected to {conn['name']} at {conn['host']}:{conn['port']}")
    except Exception as e:
        failed_conns.append(conn)
        print(f"Failed to connect to {conn['name']} at {conn['host']}:{conn['port']}")
        conn_failed = True
        pass


# script_dir = os.path.dirname(__file__)
# screenshot_dir = os.path.join(script_dir, r'screenshots')
# if not os.path.isdir(screenshot_dir):
#     os.mkdir(screenshot_dir)



# def update_screenshot():
#     width, height, channels, data = dpg.load_image('images\screenshot.png')
#     dpg.set_value("screenshot", data)



RED = [255,0,0,255]
YELLOW = [255,255,0,255]
GREEN = [0,200,0,255]
TABLE_HEADER_COLOR = (38,72,125)
TABLE_HEIGHT = 100

app_width = 400
if len(active_clients) == 0:
    app_height = 400
else:
    app_height = (TABLE_HEIGHT + 25) * len(active_conns) + 35
fail_modal_height = app_height - 175

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

# with dpg.texture_registry():
#     for client in active_clients:
#         client.save_source_screenshot(name='TEST', img_format='png', file_path=os.path.join(script_dir, f'screenshots\\{client}.png'), width=1920, height=1080, quality=100)
#         width, height, channels, data = dpg.load_image(f'screenshots\\{client}.png')
#         dpg.add_dynamic_texture(width=width, height=height, default_value=data, tag=f"screenshot_{client}")

with dpg.window(tag="Primary Window"):
    dpg.bind_font(default_font)

    with dpg.window(label="Connections Failed", modal=True, show=conn_failed, tag="connection_fail", width=app_width-100, height=fail_modal_height, pos=(50,50)):
        dpg.add_text("The following failed to connect:")
        for conn in failed_conns:
            dpg.add_text(f" - {conn['name']} - {conn['host']}:{conn['port']}")
        dpg.add_text("Make sure the config file is correct\nand that OBS is open and configured.")
        dpg.add_button(label="Close", width=-1, height=50, callback=lambda: dpg.configure_item("connection_fail", show=False))

    for client in active_clients:
        conn = active_conns[active_clients.index(client)]
        with dpg.table(header_row=True, resizable=False, width=-1, height=TABLE_HEIGHT, 
                        borders_innerH=True, borders_outerH=True, borders_innerV=True, borders_outerV=True):
            dpg.add_table_column(label=conn['name'])
            dpg.add_table_column(label=f'{conn["host"]}:{conn["port"]}')
            with dpg.table_row():
                dpg.add_text(f"{client.get_video_settings().base_width}x{client.get_video_settings().base_height}")
                dpg.add_text(f"Error!", tag=f"fps_{conn}")
            with dpg.table_row():
                dpg.add_text("Error!", tag=f"recording_status_{conn}")
                dpg.add_button(label="Toggle Recording", tag=f"toggle_recording_{conn}", width=-1, callback=client.toggle_record)
            with dpg.table_row():
                dpg.add_text("Error!", tag=f"recording_pause_status_{conn}")
                dpg.add_button(label="Pause/Resume", tag=f"toggle_recording_pause_{conn}", width=-1, callback=client.toggle_record_pause)
            with dpg.table_row():
                dpg.add_text("Recording Length:")
                dpg.add_text(label="00:00:00", tag=f"time_{conn}")
        # dpg.add_image(f"screenshot_{client}", width=1920/5, height=1080/5)
                


dpg.setup_dearpygui()
dpg.create_viewport(title=f"OBS Controller - 1 Connection" if len(active_clients) == 1 else f"OBS Controller - {len(active_clients)} Connections",
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
    for client in active_clients:
        conn = active_conns[active_clients.index(client)]
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

# if os.path.isdir(screenshot_dir):
#     shutil.rmtree(screenshot_dir)