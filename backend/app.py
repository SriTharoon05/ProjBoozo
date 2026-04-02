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

# OCR Imports (Tesseract Only)
import pytesseract
from pdf2image import convert_from_bytes

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Load .env locally (Render will use Environment Variables directly)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

print(f"DEBUG - Is Groq Key loaded? {'YES' if GROQ_API_KEY else 'NO'}")

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


def generate_excel_buffer(json_data):
    """Convert JSON extracted data into an Excel file buffer."""
    try:
        records = json_data.get("data", [])
        df = pd.DataFrame(records)

        expected_columns = ["SSN", "Participant", "Amount", "Contract", "Carrier Name"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None

        df = df[expected_columns]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Payroll Data")

        output.seek(0)
        return output

    except Exception as e:
        raise ValueError(f"Failed to generate Excel: {str(e)}")


def extract_text_with_pypdf2(pdf_file):
    """Extract text from PDF using PyPDF2."""
    pdf_reader = PdfReader(pdf_file)
    extracted_text = ""

    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"

    return extracted_text.strip()


def extract_text_with_tesseract(pdf_bytes):
    """Extract text from scanned PDF using Tesseract OCR."""
    images = convert_from_bytes(pdf_bytes, dpi=150)
    full_text = ""

    for img in images:
        text = pytesseract.image_to_string(img)
        full_text += text + "\n"

    return full_text.strip()


@app.route("/download_with_image_model", methods=["POST", "OPTIONS"])
def process_with_gemini():
    """Endpoint for Gemini (Image Model) PDF processing."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        file_bytes = file.read()
        mime_type = file.mimetype

        model = genai.GenerativeModel("gemini-2.5-flash")

        contents = [
            SYSTEM_PROMPT,
            {"mime_type": mime_type, "data": file_bytes},
        ]

        response = model.generate_content(contents)

        response_text = (
            response.text.strip()
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )

        parsed_data = json.loads(response_text)

        excel_buffer = generate_excel_buffer(parsed_data)

        return send_file(
            excel_buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="Extracted_Data_Gemini.xlsx",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download_with_text_model", methods=["POST", "OPTIONS"])
def process_with_groq():
    """Endpoint for Groq (Text Model) PDF processing with OCR fallback."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        # Read bytes for OCR fallback
        pdf_bytes = file.read()

        # Reset pointer for PyPDF2 reading
        file.seek(0)

        # Step 1: Try normal text extraction
        extracted_text = extract_text_with_pypdf2(file)

        # Step 2: If no text, use OCR
        if not extracted_text.strip():
            print("⚠️ No text found using PyPDF2. Running Tesseract OCR...")
            extracted_text = extract_text_with_tesseract(pdf_bytes)

        if not extracted_text.strip():
            return jsonify({"error": "Could not extract text from PDF even with OCR."}), 400

        # Step 3: Send extracted text to Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.replace("\xa0", " ")},
                {"role": "user", "content": f"Here is the document text:\n\n{extracted_text}"},
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
        )

        response_text = chat_completion.choices[0].message.content
        clean_text = response_text.replace("\xa0", " ").strip()

        parsed_data = json.loads(clean_text)

        excel_buffer = generate_excel_buffer(parsed_data)

        return send_file(
            excel_buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="Extracted_Data_Groq.xlsx",
        )

    except Exception as e:
        print(f"\n--- CRITICAL BACKEND ERROR --- \n{str(e)}\n------------------------------\n")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)