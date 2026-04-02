import os
import json
import io
import pandas as pd
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import google.generativeai as genai
from groq import Groq
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# OCR Imports
import pytesseract
import easyocr
from pdf2image import convert_from_bytes
from PIL import Image

app = Flask(__name__)
CORS(app)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are a data extraction assistant. Extract the payroll data from the provided document or text.
Return ONLY a valid JSON object with a single key called "data". The value of "data" must be an array of objects.
Do not include markdown formatting, code blocks, or explanations.
Each object in the array must have exactly these keys: "SSN", "Participant", "Amount", "Contract", "Carrier Name".
If a specific field is missing for a participant, use null.

Example format:
{
  "data": [
    {"SSN": "123456789", "Participant": "John Doe", "Amount": "150.00", "Contract": null, "Carrier Name": "MG Trust Co"}
  ]
}
"""

# =============================
# OCR ENGINE SWITCH HERE
# =============================
OCR_ENGINE = "tesseract"   # "tesseract" or "easyocr"

# Load EasyOCR reader once (better performance)
easyocr_reader = easyocr.Reader(['en'], gpu=False)


def generate_excel_buffer(json_data):
    try:
        records = json_data.get("data", [])
        df = pd.DataFrame(records)

        expected_columns = ["SSN", "Participant", "Amount", "Contract", "Carrier Name"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None

        df = df[expected_columns]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Payroll Data')

        output.seek(0)
        return output
    except Exception as e:
        raise ValueError(f"Failed to generate Excel: {str(e)}")


def extract_text_with_pypdf2(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    extracted_text = ""

    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"

    return extracted_text.strip()


def extract_text_with_ocr(pdf_bytes):
    images = convert_from_bytes(pdf_bytes)
    full_text = ""

    for img in images:
        if OCR_ENGINE == "tesseract":
            text = pytesseract.image_to_string(img)
        elif OCR_ENGINE == "easyocr":
            result = easyocr_reader.readtext(
                img,
                detail=0,
                paragraph=True
            )
            text = "\n".join(result)
        else:
            raise ValueError("Invalid OCR_ENGINE. Use 'tesseract' or 'easyocr'.")

        full_text += text + "\n"

    return full_text.strip()


@app.route('/download_with_text_model', methods=['POST'])
def process_with_groq():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Read PDF bytes for OCR fallback
        pdf_bytes = file.read()

        # Reset file pointer so PyPDF2 can read it
        file.seek(0)

        # Step 1: Try PyPDF2 extraction
        extracted_text = extract_text_with_pypdf2(file)

        # Step 2: If PyPDF2 fails, use OCR
        if not extracted_text.strip():
            print("⚠️ No text found using PyPDF2. Running OCR...")
            extracted_text = extract_text_with_ocr(pdf_bytes)

        if not extracted_text.strip():
            return jsonify({"error": "Could not extract text from the PDF even with OCR."}), 400

        # Step 3: Send extracted text to Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.replace('\xa0', ' ')},
                {"role": "user", "content": f"Here is the document text to process:\n\n{extracted_text}"}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )

        response_text = chat_completion.choices[0].message.content
        clean_text = response_text.replace('\xa0', ' ').strip()

        parsed_data = json.loads(clean_text)
        excel_buffer = generate_excel_buffer(parsed_data)

        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Extracted_Data_Groq.xlsx'
        )

    except Exception as e:
        print(f"\n--- CRITICAL BACKEND ERROR --- \n{str(e)}\n------------------------------\n")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)