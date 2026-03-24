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

app = Flask(__name__)
# Enable CORS so your frontend can communicate with these endpoints
CORS(app) 

# Configure API Keys (Move these to environment variables in production)
# 1. Force Python to find the .env file in the current folder
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# 2. Grab the keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# 3. Quick debug print to prove it works (you can delete this later)
print(f"DEBUG - Is Groq Key loaded? {'YES' if GROQ_API_KEY else 'NO'}")

genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# The instruction set for both models to ensure uniform JSON output
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
    """Helper function to convert JSON data into a downloadable Excel buffer."""
    try:
        # Extract the list of records from the JSON response
        records = json_data.get("data", [])
        df = pd.DataFrame(records)
        
        # Ensure the columns match your required structure
        expected_columns = ["SSN", "Participant", "Amount", "Contract", "Carrier Name"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None
                
        # Reorder columns just in case the LLM mixed them up
        df = df[expected_columns]

        # Write to an in-memory buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Payroll Data')
        
        output.seek(0)
        return output
    except Exception as e:
        raise ValueError(f"Failed to generate Excel: {str(e)}")


@app.route('/download_with_image_model', methods=['POST'])
def process_with_gemini():
    """Endpoint for the 'Download with image model' button."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Read file bytes and determine mime type
        file_bytes = file.read()
        mime_type = file.mimetype

        # Gemini 1.5 Flash natively supports both images and PDFs natively
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Pass the prompt and the raw file data to Gemini
        contents = [
            SYSTEM_PROMPT,
            {"mime_type": mime_type, "data": file_bytes}
        ]
        
        response = model.generate_content(contents)
        
        # Clean the response in case the model adds markdown formatting like ```json
        response_text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
        parsed_data = json.loads(response_text)
        
        excel_buffer = generate_excel_buffer(parsed_data)
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Extracted_Data_Gemini.xlsx'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download_with_text_model', methods=['POST'])
def process_with_groq():
    """Endpoint for the 'Download with text model' button."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # Extract text using PyPDF2
        pdf_reader = PdfReader(file)
        extracted_text = ""
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() + "\n"

        if not extracted_text.strip():
            return jsonify({"error": "Could not extract text from the PDF. It might be a scanned image."}), 400

        # Pass the extracted text to Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.replace('\xa0', ' ')}, # Scrub hidden chars from prompt
                {"role": "user", "content": f"Here is the document text to process:\n\n{extracted_text}"}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"} 
        )
        
        # 1. Grab the content (The MUST be here)
        response_text = chat_completion.choices[0].message.content
        
        # 2. Scrub any hidden non-breaking spaces before JSON parsing
        clean_text = response_text.replace('\xa0', ' ').strip()
        
        # 3. Parse and build the Excel file
        parsed_data = json.loads(clean_text)
        excel_buffer = generate_excel_buffer(parsed_data)
        
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Extracted_Data_Groq.xlsx'
        )

    except Exception as e:
        # This will print the EXACT error to your terminal so we aren't guessing!
        print(f"\n--- CRITICAL BACKEND ERROR --- \n{str(e)}\n------------------------------\n")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(debug=True, port=5000)