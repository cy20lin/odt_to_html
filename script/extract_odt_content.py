import zipfile
import os
import shutil

def extract_odt_content(odt_file_path, output_xml_path):
    """
    Extracts the 'content.xml' from an ODT file and saves it to a specified path.

    Args:
        odt_file_path (str): The path to the input .odt file.
        output_xml_path (str): The path where the output content.xml should be saved.
    """
    try:
        # Open the ODT file as a zip archive
        with zipfile.ZipFile(odt_file_path, 'r') as zf:
            # Check if 'content.xml' exists within the archive
            if 'content.xml' in zf.namelist():
                # Extract 'content.xml' to the specified output path
                source = zf.open('content.xml')
                with open(output_xml_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
                print(f"Successfully extracted 'content.xml' to: {output_xml_path}")
            else:
                print(f"Error: 'content.xml' not found in {odt_file_path}")
    except FileNotFoundError:
        print(f"Error: The file '{odt_file_path}' was not found.")
    except zipfile.BadZipFile:
        print(f"Error: '{odt_file_path}' is not a valid ODT/ZIP file.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

import argparse
import sys

def main():
    """
    Parses command-line arguments and performs a simple action.
    """
    # Create the parser
    parser = argparse.ArgumentParser(description="A simple CLI script accepting two arguments.")

    # Add the arguments
    parser.add_argument(
        'input_file',
        type=str,
        help='The path to the input file.'
    )
    
    parser.add_argument(
        'output_file',
        type=str,
        help='The path where the output should be saved.'
    )

    # Parse the arguments from the command line
    args = parser.parse_args()

    # Access the arguments and perform an action
    print(f"Input file specified: {args.input_file}")
    print(f"Output file specified: {args.output_file}")

    extract_odt_content(args.input_file, args.output_file)


if __name__ == "__main__":
    # Ensure the script runs only when executed directly
    main()