import argparse
from inscriptis import get_text
import sys
import os

def convert_html_to_txt(input_path, output_path):
    """
    Converts an HTML file from input_path to plain text, saving it to output_path.
    """
    try:
        # Open and read the HTML file content
        with open(input_path, 'r', encoding='utf-8') as f_in:
            html_content = f_in.read()
        
        # Convert the HTML content to plain text using inscriptis
        text_content = get_text(html_content)
        
        # Open and write the text content to the output file
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(text_content)
            
        print(f"Successfully converted '{input_path}' to '{output_path}'")

    except FileNotFoundError:
        print(f"Error: The file '{input_path}' was not found.", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading/writing files: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """
    Main function to parse command-line arguments and run the conversion.
    """
    parser = argparse.ArgumentParser(description="Convert an HTML file to plain text using Inscriptis.")
    
    # Add the input path argument
    parser.add_argument(
        "inputpath", 
        type=str, 
        help="The path to the input HTML file."
    )
    
    # Add the output path argument
    parser.add_argument(
        "outputpath", 
        type=str, 
        help="The path where the output text file will be saved."
    )
    
    args = parser.parse_args()
    
    # Ensure input file exists before attempting conversion
    if not os.path.exists(args.inputpath):
        print(f"Error: Input file not found at '{args.inputpath}'", file=sys.stderr)
        sys.exit(1)

    convert_html_to_txt(args.inputpath, args.outputpath)

if __name__ == "__main__":
    main()
