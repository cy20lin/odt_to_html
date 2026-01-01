from html2image import Html2Image

from PIL import Image
import os

def convert_transparent_to_white(input_path, output_path):
    """
    Converts a PNG image with a transparent background to one with a white background.

    Args:
        input_path (str): The path to the input transparent PNG file.
        output_path (str): The path to save the output image with a white background.
    """
    # Open the input image
    try:
        image = Image.open(input_path)
    except IOError:
        print(f"Error: Unable to open image at {input_path}")
        return

    # Check if the image has an alpha channel (transparency)
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        # Create a new background image with white color
        # 'RGB' mode is used for the output, and the size matches the input image
        background = Image.new("RGB", image.size, (255, 255, 255))

        # Paste the original image onto the white background using the alpha channel as a mask
        # The alpha channel determines how the images are blended
        background.paste(image, (0, 0), image)

        # Save the resulting image
        background.save(output_path)
        print(f"Successfully converted and saved to {output_path}")

    else:
        print(f"Image at {input_path} does not have a transparency layer. Copying directly.")
        # If no transparency, simply convert to RGB and save (or just copy)
        image.convert("RGB").save(output_path)

import sys
import pathlib
import os

if __name__ == "__main__":
    argv = sys.argv
    default_target = 'png'
    print(f'trace args={argv}')
    # Define your input file and desired output directory
    if len(argv) < 2:
        print("Error: input_file_path not specified.")
        print("")
        print("Usage: python <this-script.py> /path/to/input.html [/path/to/output.png]")
        print("")
        sys.exit(1)
    input_file_path = pathlib.Path(argv[1]).absolute()
    input_file_path_str = pathlib.Path(argv[1]).absolute().as_posix()
    print(f'trace input_file_path: {input_file_path}')
    if len(argv) < 3:
        output_file_path = input_file_path.with_suffix('.'+default_target)
    else:
        output_file_path = input_file_path.parent / argv[2]
    output_file_path_str = output_file_path.as_posix()
    target = output_file_path.suffix[1:]
    ext = '.' + target
    print(f'trace output_file_path: {output_file_path}')

    # output_tmp_dir = (pathlib.Path(__file__).parent / 'tmp').absolute()
    # output_tmp_file_path = (output_tmp_dir / input_file_path.name).with_suffix(ext)
    # print(f'trace output_tmp_dir: {output_tmp_dir}')
    # print(f'trace output_tmp_file_path: {output_tmp_file_path}')
    print(f'trace target type: {target}')
    # output_tmp_dir.mkdir(parents=True, exist_ok=True)
    input_odt_file_path = pathlib.Path(sys.argv[1]).absolute().as_posix()
    try:
        # hti = Html2Image(browser='edge', size=(817,1057), output_path=output_file_path.parent)
        hti = Html2Image(browser='edge', size=(540,960), output_path=output_file_path.parent)
        # hti = Html2Image(browser='edge', output_path=output_file_path.parent)
        hti.screenshot(html_file=input_file_path.as_posix(), save_as=output_file_path.name)
        convert_transparent_to_white(output_file_path.as_posix(), output_file_path.as_posix())
    except Exception as e:
        print(f"Error: Internal error when converting, reason = {e}")
        sys.exit(1)
    sys.exit(0)
