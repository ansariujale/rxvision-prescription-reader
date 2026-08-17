
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



def extract_text_from_image(image_path, medicine_dataset):
    """Extract only medicine names from the image.

    Always uses AWS Textract. This used to try Tesseract first and escalate
    to Textract below a confidence threshold, but measurement
    (docs/evaluation-log.md) found Tesseract read zero of 85 medicines on
    real handwritten prescriptions, and its confidence score doesn't predict
    that failure - a third of images kept Tesseract's empty result instead of
    escalating. There's no signal left to route on, so this always pays for
    Textract rather than gambling on Tesseract's confidence being right.
    """
    medicine_names = load_medicine_dataset(medicine_dataset)

    try:
        extracted_text = extract_text_with_textract(image_path)
    except Exception as e:
        print(f"Error during Textract processing: {e}")
        return ""

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
