import cv2
import numpy as np
import os


def create_temp_directory():
    """Create a temporary directory to store processed images."""
    try:
        if not os.path.exists("temp"):
            os.makedirs("temp")
    except PermissionError:
        print("Permission denied: unable to create 'temp' directory.")
    except Exception as e:
        print(f"An error occured while creating 'temp' directory {e}")

def load_image(image_path):
    """Load the image from the specified path."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"Error: Unable to load image at {image_path}")
        return img
    except FileNotFoundError:
        print(f"Error: File not found at {image_path}:")
        return None
    except Exception as e:
        print(f"An error occured while loading the image: {e}")


def invert_image(image):
    """Invert the colors of the image."""
    try:
        return cv2.bitwise_not(image)
    except Exception as e:
        print(f"An error occured while inverting the image: {e}")
        return image  # Return the original image if inversion fails
    
def grayscale(image):
    """Convert the image to grayscale."""
    try:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except Exception as e:
        print(f"An error occurred while converting to grayscale: {e}")
        return image #Return the original image if grayscale conversion fails

def binarize(image):
    """Convert the grayscale image to binary."""
    try:
        adaptive_thresh_image = cv2.adaptiveThreshold(
            image, 255,                          
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,      
            cv2.THRESH_BINARY,                  
            11,                                  
            2                                  
        )
        
    except Exception as e:
        print(f"An error occurred while binarizing the image: {e}")
        return image # Return the original image if binarization fails

    return adaptive_thresh_image

def noise_removal(image):
    """Remove noise from the image."""
    try:    
        kernel = np.ones((1, 1), np.uint8)
        noise_removed_image = cv2.dilate(image, kernel, iterations=1)
        noise_removed_image = cv2.erode(noise_removed_image, kernel, iterations=1)
        noise_removed_image = cv2.morphologyEx(noise_removed_image, cv2.MORPH_CLOSE, kernel)
        noise_removed_image = cv2.medianBlur(noise_removed_image, 3)
        
    except Exception as e:
        print(f"An error occurred while removing noise: {e}")
        return image # Return the original image if noise removal fails

    return noise_removed_image

def apply_dynamic_erosion(image):
    """Dynamically apply erosion based on the number of connected components."""

    eroded_image = image
    try:
        # Find connected components in the binary image
        num_labels, labels = cv2.connectedComponents(image)

        # Threshold to decide whether to apply erosion or not
        
        if num_labels < 30:  # This threshold can be adjusted based on your data
            kernel = np.ones((2, 2), np.uint8)
            eroded_image = cv2.erode(image, kernel, iterations=1)
        else:
            print("Skipping erosion, the image seems fine.")
            
    except Exception as e:
        print(f"An error occurred while applying dynamic erosion: {e}")
        return image # Return the original image and False if erosion fails

    return eroded_image

def apply_dynamic_dilation(image):
    """Dynamically apply dilation based on the number of connected components."""
    dilated_image = image
    try:
        # Find connected components in the binary image
        num_labels, labels = cv2.connectedComponents(image)
        # Boolean flag to track whether dilation was applied
        # Threshold to decide whether to apply dilation or not
        if num_labels > 100:  # This threshold can be adjusted based on your data
            kernel = np.ones((2, 2), np.uint8)
            dilated_image = cv2.dilate(image, kernel, iterations=1)
        else:
            print("Skipping dilation, the image seems fine.")
    except Exception as e:
        print(f"An error occured while dilating the image: {e}")
        return image # Return the original image and False if dilation fails
        
    return dilated_image

def rotate_image(image):
    (h,w)= image.shape[:2]

    # Check if the image is in portrait mode (height > width)
    try:
        if h>w:
            print("Image is in portrait mode (height>width)")
            #Rotate image by 90 degree , rotating landscape mode
            rotate_image= cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            
        else:
            print("Image is in landscape mode (width>height) No rotation needed.")
            return image
    except Exception as e:
        print(f"error while rotating the image: {e}")
        return image # Return the original image if image rotation fails
    return rotate_image     

PREPROCESSING_STEPS= [
        ("grayscale", grayscale),
        ("binarization", binarize),
        ("noise_removal", noise_removal),
        ("erosion", apply_dynamic_erosion),
        ("dilation", apply_dynamic_dilation),
        ("rotate", rotate_image)
    ]


def process_image(path):
    """Process the image by applying all preprocessing techniques"""
    create_temp_directory()
    image = load_image(path)
    final_image = image # Initialize final_image with the original path in case no processing is done

    for name, step in PREPROCESSING_STEPS:
        image = step(image)
        cv2.imwrite(f"temp/{name}.jpg", image)
        print(f"{name.capitalize()}: Image saved as temp/{name}.jpg")
        final_image = image #update final_image after each step
    return final_image