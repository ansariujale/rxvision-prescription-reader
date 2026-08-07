
import pytesseract
from PIL import Image
from preprocessing import process_image
import pandas as pd
import boto3
from rapidfuzz import fuzz, process

#initialize the aws textract client
textract_client= boto3.client("textract", region_name= "ap-south-1")

medicine_dataset=r"resource/medicine_names.csv"

# Load the medicine dataset
def load_medicine_dataset(medicine_dataset):
    """Load medicine names from the dataset."""
    df = pd.read_csv(medicine_dataset)
    return [name.lower().strip() for name in df['name'].tolist()]

GENERIC_WORDS = ["tablet", "syrup","suspension", "capsule", "ointment", "mg", "ml", "cream", "Injection","","10", "20", "5", "60", "100"]

def is_valid_medicine_name(text):
    for word in GENERIC_WORDS:
        if word in text.split():
            return False
        return True

def normalize_text(text):
    return text.lower().replace("mg", "").strip()


#get the confidence score from tesseract to decide whether to fall back to textract
def get_tesseract_confidence(image):

    """Get confidence score for Tesseract OCR"""
    # Use pytesseract to confidences get detailed information
    data= pytesseract.image_to_data(image, output_type= pytesseract.Output.DICT)

    # Drop the -1 rows. Those are Tesseract's page/block/paragraph/line entries
    # rather than recognised words, and they have no confidence score.
    #
    # This used to compare against the string '-1', but pytesseract hands back
    # ints, so nothing was ever filtered and every -1 was averaged in as if it
    # were a real score. On a page Tesseract read perfectly that reported 43
    # instead of 95, which pushed every image past the escalation threshold and
    # sent the lot to Textract.
    confidences = [int(conf) for conf in data['conf'] if int(conf) != -1]

    #return average confidence score
    return sum(confidences)/len(confidences) if confidences else 0

# Match extracted text against medicine
def match_medicine(extracted_text, medicine_names, threshold=68): #default threshold = 68
    """Match extracted text with the medicine dataset."""
    results = []
    for text in extracted_text.split("\n"):
        text = normalize_text(text.strip())
        normalized_dataset = [normalize_text(name) for name in medicine_names]  # Normalize dataset
        match= process.extractOne(text,normalized_dataset,scorer=fuzz.token_sort_ratio)
        if match and match[1]>=threshold:
            
            results.append(match[0])
    return results

def extract_text_with_textract(image_path):
    """Extract text from an image using AWS Textract."""
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    response = textract_client.detect_document_text(Document={"Bytes": image_bytes})

    extracted_text = ""
    for item in response["Blocks"]:
        if item["BlockType"] == "LINE":  # Extract line-level text
            extracted_text += item["Text"] + "\n"

    return extracted_text



def extract_text_from_image(image_path,medicine_dataset,confidence_threshold=70): #default threshold = 70
    """Extract only medicine names from the image.

    Runs Tesseract first and falls back to AWS Textract when Tesseract's own
    mean confidence comes in under the threshold.
    """
    # Load the medicine dataset
    medicine_names = load_medicine_dataset(medicine_dataset)

    # Load the preprocessed image using Pillow
    preprocessed_image = Image.open(image_path)

    # Custom Tesseract configurations for better results
    custom_config = r'--oem 3 --psm 6'  # Use best OCR engine mode and automatic page segmentation

    # Step 1: Try the Tesseract OCR first with custom configuration
    extracted_text = pytesseract.image_to_string(preprocessed_image, lang='eng', config=custom_config)

    # Get Tesseract confidence score
    confidence = get_tesseract_confidence(preprocessed_image)

    # Step 2: If confidence is low, hand the image to Textract instead
    if confidence < confidence_threshold:
        try:
            extracted_text = extract_text_with_textract(image_path)
        except Exception as e:
            print(f"Error during Textract processing: {e}")
            return ""

    # Step 3: Match extracted text with medicine dataset
    results = match_medicine(extracted_text, medicine_names)
    return results


# Kept for standalone testing
# if __name__ == "__main__":
#      # Paths to files
#     image_path = r"C:\Users\aujal\OneDrive\Desktop\Testing Images\image (23).jpg"
#     dataset_path = r"resource\medicine_names.csv"
#     # Extract medicine names
#     extracted_text = extract_text_from_image(image_path,medicine_dataset)
    
#     # Display the extracted medicine names
#     print("Extracted Medicine Names:\n",extracted_text)
