"""
This will get the current preview scene from OBS and save a screenshot of it to the images folder. 
It will then display the screenshot in a window and update the screenshot when the button is pressed.
This is a proof of concept for how to display a screenshot in a window in DearPyGui.
Automatic updating and multiple clients are needed to implement this in the OBS Controller.
"""

import os, shutil
import dearpygui.dearpygui as dpg
import obsws_python as obs

client = obs.ReqClient(host='localhost', port=4455, timeout=1)

if not os.path.isdir(r".\images"):
    os.mkdir(r".\images")

#get script dir
script_dir = os.path.dirname(__file__)
#join script dir with image dir
image_dir = os.path.join(script_dir, r'images\screenshot.png')

program_scene = client.get_current_program_scene()
client.save_source_screenshot(name=program_scene.current_program_scene_name, img_format='png', file_path=image_dir, width=1920, height=1080, quality=100)

def update_screenshot():
    client.save_source_screenshot(name=program_scene.current_program_scene_name, img_format='png', file_path=image_dir, width=1920, height=1080, quality=100)
    width, height, channels, data = dpg.load_image('images\screenshot.png')
    dpg.set_value("screenshot", data)

# show the screenshot in dpg
dpg.create_context()

width, height, channels, data = dpg.load_image('images\screenshot.png')

with dpg.texture_registry(show=True):
    dpg.add_dynamic_texture(width=width, height=height, default_value=data, tag="screenshot")

with dpg.window(tag="Screenshot"):
    dpg.add_image("screenshot", width=width/2, height=height/2)
    dpg.add_button(label="Update Screenshot", width=-1, height=50, callback=update_screenshot)

dpg.setup_dearpygui()
dpg.create_viewport(title=f"Screenshot Test", width=1000, height=700)
dpg.show_viewport()
dpg.set_primary_window("Screenshot", True)

while dpg.is_dearpygui_running():
    dpg.render_dearpygui_frame()

if os.path.isdir(r".\images"):
    shutil.rmtree(r".\images")
