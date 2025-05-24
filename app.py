import gradio as gr
from new_v4 import GroqOutlineConverter
import os
import glob
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")

# Directory to store generated DOCX files
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Optional: Cleanup old DOCX files
for f in glob.glob(f"{OUTPUT_FOLDER}/*.docx"):
    os.remove(f)

def convert_pdf_to_outline(pdf_path):
    if not pdf_path:
        return "No PDF file provided.", None
    if not API_KEY:
        return "Groq API key not set. Please define GROQ_API_KEY in your .env file.", None

    try:
        converter = GroqOutlineConverter(api_key=API_KEY)
    except Exception as e:
        return f"Failed to initialize Groq client: {e}", None

    # Generate output path with unique filename
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_filename = f"{base_name}_styled_outline.docx"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    result_path = converter.process_file(pdf_path, output_path)

    if result_path and os.path.exists(result_path):
        return "Successfully converted!", result_path
    else:
        return "Failed to generate outline.", None

# Gradio interface
gr.Interface(
    fn=convert_pdf_to_outline,
    inputs=gr.File(label="Upload PDF", type="filepath"),
    outputs=[
        gr.Textbox(label="Status"),
        gr.File(label="Download Styled DOCX")
    ],
    title="PrettyNotes",
    description="Upload a PDF and get a structured, styled outline in DOCX format using Groq AI. Your API key is loaded automatically from the environment."
).launch()

