"""
This will get the current preview scene from OBS and save a screenshot of it to the images folder. 
It will then display the screenshot in a window and update the screenshot when the button is pressed.
This is a proof of concept for how to display a screenshot in a window in DearPyGui.
Automatic updating and multiple clients are needed to implement this in the OBS Controller.
"""
import base64, cv2
import dearpygui.dearpygui as dpg
import io
import numpy as np
from PIL import Image
import obsws_python as obs

client = obs.ReqClient(host='localhost', port=4455, timeout=1)

program_scene = client.get_current_program_scene()
screenshot_data = client.get_source_screenshot(name=program_scene.current_program_scene_name, img_format='jpg', width=1920, height=1080, quality=-1)

base64_string = screenshot_data.image_data.replace('data:image/jpg;base64,', '')
# decoded = base64.b64decode(base64_string)
# nparr = np.frombuffer(decoded, np.uint8)
# image_array = [float(i) for i in nparr]
# # Add alpha channel to image_array by adding 255 to every 4th element
# alpha_image_array = [i if (index + 1) % 4 != 0 else 255.0 for index, i in enumerate(image_array)]
# print(alpha_image_array)
# print(len(alpha_image_array))

def decode_base64_to_image(base64_string):
    # Decode base64 string into bytes
    image_bytes = base64.b64decode(base64_string)

    # Create PIL Image object from bytes
    image = Image.open(io.BytesIO(image_bytes))

    # Convert PIL Image to numpy array
    image_array = np.asarray(image, dtype=np.uint8)

    # Add alpha channel to image_array by inserting 255 every 4th element
    alpha_image_array = np.insert(image_array, 3, 255, axis=2)

    # Reshape the image array to 1D RGBA array
    image_array_1d = alpha_image_array.reshape(-1, 4)

    # Convert the array to floats and subtract 100 from each number
    image_array_1d = [float(i)/255 for i in image_array_1d.flatten()]

    return image_array_1d

texture_data = decode_base64_to_image(base64_string)
print(len(texture_data)/4/1920)

def update_screenshot(screenshot_data):
    # screenshot_data = client.get_source_screenshot(name=program_scene.current_program_scene_name, img_format='jpg', width=1920, height=1080, quality=0)
    # dpg.set_value("screenshot", screenshot_data)
    print("Updating screenshot")

# show the screenshot in dpg
dpg.create_context()

with dpg.texture_registry(show=True):
    dpg.add_dynamic_texture(width=1920, height=1080, default_value=texture_data, tag="screenshot")

with dpg.window(tag="Screenshot Window"):
    dpg.add_image("screenshot", width=1920/2, height=1080/2)
    dpg.add_button(label="Update Screenshot", width=-1, height=50)

dpg.setup_dearpygui()
dpg.create_viewport(title=f"Screenshot Test", width=1000, height=700)
dpg.show_viewport()
dpg.set_primary_window("Screenshot Window", True)

while dpg.is_dearpygui_running():
    dpg.set_viewport_title(f"Screenshot Test - {dpg.get_frame_rate()} fps")
    dpg.render_dearpygui_frame()
