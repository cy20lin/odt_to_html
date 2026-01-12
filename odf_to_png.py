import subprocess
import os

def convert_odt_to_png(input_file, output_dir, type='png'):
    """
    Converts an ODT file to PNG images using the soffice command-line tool.

    Args:
        input_file (str): The path to the input .odt file.
        output_dir (str): The directory where output PNG files will be saved.
    """
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Command to run: soffice --headless --convert-to png input_file --outdir output_dir
    # --headless runs the application without a GUI
    command = [
        'soffice',
        '--headless',
        '--invisible',
        '--convert-to',
        type,
        input_file,
        '--outdir',
        output_dir
    ]

    try:
        # Run the command
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Successfully converted {input_file} to PNG in {output_dir}")
        # Note: Multi-page ODT files will generate multiple PNG files (e.g., filename-0.png, filename-1.png)
    except FileNotFoundError:
        print("Error: 'soffice' command not found. Make sure LibreOffice/OpenOffice is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e.stderr}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

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
        print("Usage: python <this-script.py> /path/to/input.odt [/path/to/output.png]")
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

    output_tmp_dir = (pathlib.Path(__file__).parent / 'tmp').absolute()
    output_tmp_file_path = (output_tmp_dir / input_file_path.name).with_suffix(ext)
    print(f'trace output_tmp_dir: {output_tmp_dir}')
    print(f'trace output_tmp_file_path: {output_tmp_file_path}')
    print(f'trace target type: {target}')
    output_tmp_dir.mkdir(parents=True, exist_ok=True)
    input_odt_file_path = pathlib.Path(sys.argv[1]).absolute().as_posix()
    try:
        convert_odt_to_png(input_file_path.as_posix(), output_tmp_dir, target)
        if output_file_path != output_tmp_file_path:
            os.replace(output_tmp_file_path, output_file_path)
    except Exception as e:
        print(f"Error: Internal error when converting, reason = {e}")
        sys.exit(1)
    sys.exit(0)
