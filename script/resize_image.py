import argparse
from PIL import Image
import os

def resize_image(input_path, output_path, width, height):
    """Resizes an image to the specified width and height."""
    try:
        with Image.open(input_path) as img:
            # Resize the image
            resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Save the resized image
            resized_img.save(output_path)
            print(f"Successfully resized image and saved to: {output_path}")
            print(f"New dimensions: {width}x{height}")
            
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_path}'")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Resize an image to a specified width and height.")
    
    parser.add_argument("input_image_path", type=str, help="Path to the input image file.")
    parser.add_argument("output_image_path", type=str, help="Path for the output resized image file.")
    parser.add_argument("width", type=int, help="Desired output width in pixels.")
    parser.add_argument("height", type=int, help="Desired output height in pixels.")
    
    # Parse the arguments from the command line
    args = parser.parse_args()
    
    # Call the resize function with the parsed arguments
    resize_image(args.input_image_path, args.output_image_path, args.width, args.height)

