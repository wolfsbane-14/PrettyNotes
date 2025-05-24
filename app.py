import gradio as gr
from new_v4 import GroqOutlineConverter
import os

def generate_outline(pdf_file, api_key):
    if not api_key:
        return "", "Error: Groq API Key is required."
    
    try:
        converter = GroqOutlineConverter(api_key=api_key)
        output_path = converter.process_file(pdf_file.name)
        if output_path and os.path.exists(output_path):
            return output_path, "Success! Download your styled DOCX."
        return "", "Failed to generate outline."
    except Exception as e:
        return "", f"Error: {str(e)}"

iface = gr.Interface(
    fn=generate_outline,
    inputs=[
        gr.File(label="Upload PDF File", file_types=[".pdf"]),
        gr.Textbox(label="Enter GROQ API Key", type="password")
    ],
    outputs=[
        gr.File(label="Download Styled DOCX Outline"),
        gr.Textbox(label="Status Message")
    ],
    title="PDF to Styled Outline DOCX Converter",
    description="Upload a PDF and get a highlighted, structured outline in DOCX format powered by Groq API."
)

if __name__ == "__main__":
    iface.launch()

