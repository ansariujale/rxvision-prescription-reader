from text_extraction import extract_text_from_image


MEDICINE_DATASET_PATH = r"resource/medicine_names.csv"

def processAndExtract(image_path):
    """Extract medicine names from a prescription image via AWS Textract."""
    extracted_text = extract_text_from_image(image_path, MEDICINE_DATASET_PATH)
    print(extracted_text)
    return extracted_text

# image_path=r"C:\Users\aujal\OneDrive\Desktop\Testing Images\image (23).jpg"
# processAndExtract(image_path)