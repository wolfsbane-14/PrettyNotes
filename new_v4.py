import os
import re
import fitz  # PyMuPDF
from groq import Groq
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Configuration for chunking
MAX_CHARS_PER_CHUNK = 12000

# --- Style Configuration ---
# Fonts (adjust based on what's available and desired, 'Courier New' is often a good monospace choice)
HIERARCHY_MARKER_FONT_NAME = 'Courier New'
TITLE_TEXT_FONT_NAME = 'Courier New'
SUBTITLE_TEXT_FONT_NAME = 'Courier New'
CONTENT_TEXT_FONT_NAME = 'Courier New'

# Font Sizes
HEADING_FONT_SIZE = 14
BODY_FONT_SIZE = 12

# Keywords to highlight and their colors (hex) - IDE-style syntax highlighting
KEYWORDS_TO_HIGHLIGHT = {
    # Control flow and logical operators (Magenta - high contrast)
    "and": "FF00FF", # No # in docx colors
    "or": "FF00FF",
    "not": "FF00FF",
    "if": "FF00FF",
    "then": "FF00FF",
    "else": "FF00FF",
    "when": "FF00FF",
    "while": "FF00FF",
    "for": "FF00FF",
    "in": "FF00FF",
    "with": "FF00FF",
    "by": "FF00FF",

    # Prepositions and connectors (Bright Blue)
    "to": "007ACC",
    "into": "007ACC",
    "from": "007ACC",
    "of": "007ACC",
    "at": "007ACC",
    "on": "007ACC",
    "through": "007ACC",
    "via": "007ACC",
    "over": "007ACC",
    "under": "007ACC",
    "between": "007ACC",
    "among": "007ACC",

    # Important verbs (Vivid Teal/Green)
    "is": "00D8B0",
    "are": "00D8B0",
    "was": "00D8B0",
    "were": "00D8B0",
    "will": "00D8B0",
    "can": "00D8B0",
    "should": "00D8B0",
    "must": "00D8B0",
    "may": "00D8B0",
    "could": "00D8B0",
    "would": "00D8B0",

    # Business/academic keywords (Bright Yellow-Gold)
    "strategic": "FFD700",
    "management": "FFD700",
    "analysis": "FFD700",
    "framework": "FFD700",
    "methodology": "FFD700",
    "approach": "FFD700",
    "implementation": "FFD700",
    "evaluation": "FFD700",
    "assessment": "FFD700",
    "development": "FFD700",
    "research": "FFD700",
    "study": "FFD700",
    "process": "FFD700",
    "system": "FFD700",
    "model": "FFD700",
    "theory": "FFD700",

    # Human-related terms (Striking Light Green)
    "human": "A6E22E",
    "people": "A6E22E",
    "individual": "A6E22E",
    "person": "A6E22E",
    "employee": "A6E22E",
    "worker": "A6E22E",
    "staff": "A6E22E",
    "team": "A6E22E",
    "group": "A6E22E",
    "organization": "A6E22E",
    "company": "A6E22E",
    "business": "A6E22E",

    # Resource-related terms (Bright Cyan)
    "resource": "00BFFF",
    "data": "00BFFF",
    "information": "00BFFF",
    "knowledge": "00BFFF",
    "skill": "00BFFF",
    "capability": "00BFFF",
    "capacity": "00BFFF",
    "asset": "00BFFF",
    "tool": "00BFFF",
    "method": "00BFFF",
    "technique": "00BFFF",
    "solution": "00BFFF",

    # Quantifiers and measures (Bright Orange)
    "all": "FF8C00",
    "some": "FF8C00",
    "many": "FF8C00",
    "few": "FF8C00",
    "most": "FF8C00",
    "several": "FF8C00",
    "various": "FF8C00",
    "multiple": "FF8C00",
    "single": "FF8C00",
    "first": "FF8C00",
    "second": "FF8C00",
    "third": "FF8C00",
    "primary": "FF8C00",
    "secondary": "FF8C00",
    "main": "FF8C00",
    "key": "FF8C00",
    "important": "FF8C00",
    "critical": "FF8C00",
    "essential": "FF8C00",
    "significant": "FF8C00",
}

DEFAULT_TEXT_COLOR = "000000"  # Black for default text

# Bullet prefix (using the one LLM is trained on for parsing consistency)
BULLET_PREFIX = "|-- "
# --- End Style Configuration ---

class GroqOutlineConverter:
    def __init__(self, api_key=None):
        """Initialize the converter with Groq API"""
        try:
            self.client = Groq(api_key=api_key)
            print("Groq client initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize Groq client: {e}")
            print("Please ensure the GROQ_API_KEY environment variable is set, or pass a valid api_key.")
            raise

        self.model_name = "deepseek-r1-distill-llama-70b"

    def _format_text_for_docx(self, paragraph, text_content, text_font_name, text_color, is_bold=False):
        """Applies keyword highlighting and styling to a docx paragraph."""
        if not text_content:
            return

        # Use a temporary string and process it, then add runs to the paragraph
        temp_text = text_content
        
        # Sort keywords by length descending to match longer keywords first and avoid partial matches
        sorted_keywords = sorted(KEYWORDS_TO_HIGHLIGHT.keys(), key=len, reverse=True)

        # Regex to find all occurrences of keywords, including overlaps if desired
        # This one handles non-overlapping matches effectively
        
        # Find all keyword matches and their positions
        matches = []
        for keyword in sorted_keywords:
            pattern = r'\b(' + re.escape(keyword) + r')\b'
            for match in re.finditer(pattern, temp_text, re.IGNORECASE):
                matches.append((match.start(), match.end(), match.group(1), KEYWORDS_TO_HIGHLIGHT[keyword]))
        
        # Sort matches by their start position to process them in order
        matches.sort(key=lambda x: x[0])

        last_idx = 0
        for start, end, matched_word, color in matches:
            # Add text before the highlighted keyword
            if start > last_idx:
                run = paragraph.add_run(temp_text[last_idx:start])
                run.font.name = text_font_name
                run.font.size = Pt(BODY_FONT_SIZE)
                run.font.color.rgb = self._hex_to_rgb(DEFAULT_TEXT_COLOR)
                run.bold = is_bold
            
            # Add the highlighted keyword
            run = paragraph.add_run(matched_word)
            run.font.name = text_font_name
            run.font.size = Pt(BODY_FONT_SIZE)
            run.font.color.rgb = self._hex_to_rgb(color)
            run.bold = True # Highlighted keywords are always bold
            
            last_idx = end
        
        # Add any remaining text after the last highlighted keyword
        if last_idx < len(temp_text):
            run = paragraph.add_run(temp_text[last_idx:])
            run.font.name = text_font_name
            run.font.size = Pt(BODY_FONT_SIZE)
            run.font.color.rgb = self._hex_to_rgb(DEFAULT_TEXT_COLOR)
            run.bold = is_bold
            
        # Ensure the paragraph has at least one run if it was empty initially
        if not paragraph.runs and text_content:
            run = paragraph.add_run(text_content)
            run.font.name = text_font_name
            run.font.size = Pt(BODY_FONT_SIZE)
            run.font.color.rgb = self._hex_to_rgb(DEFAULT_TEXT_COLOR)
            run.bold = is_bold

    def _hex_to_rgb(self, hex_color):
        """Converts a hex color string (e.g., "RRGGBB") to an RGB object for python-docx."""
        from docx.shared import RGBColor
        hex_color = hex_color.lstrip('#')
        return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

    def extract_text_from_pdf(self, pdf_path):
        """Extract text content from all pages of a PDF."""
        print(f"Extracting text from PDF: {pdf_path}")
        try:
            doc = fitz.open(pdf_path)
            full_text = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                full_text.append(page.get_text("text"))
            doc.close()
            extracted_text = "\n".join(full_text)
            if not extracted_text.strip():
                print("Warning: No text extracted from the PDF. The PDF might be image-based or empty.")
            return extracted_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return None

    def split_text_into_chunks(self, text, max_chars=MAX_CHARS_PER_CHUNK):
        """Splits text into chunks, trying to respect paragraph boundaries."""
        chunks = []
        current_chunk_paras = []
        current_length = 0
        paragraphs = text.split('\n\n')

        for para_idx, paragraph in enumerate(paragraphs):
            para_len = len(paragraph)
            if current_length + para_len + (2 if current_chunk_paras else 0) <= max_chars:
                current_chunk_paras.append(paragraph)
                current_length += para_len + (2 if current_chunk_paras else 0)
            else:
                if current_chunk_paras:
                    chunks.append("\n\n".join(current_chunk_paras))
                
                if para_len > max_chars:
                    start = 0
                    while start < para_len:
                        end = start + max_chars
                        chunks.append(paragraph[start:end])
                        start = end
                    current_chunk_paras = [] 
                    current_length = 0
                else: 
                    current_chunk_paras = [paragraph]
                    current_length = para_len
            
            if para_idx == len(paragraphs) - 1 and current_chunk_paras:
                chunks.append("\n\n".join(current_chunk_paras))
        
        return [chunk for chunk in chunks if chunk.strip()]

    def process_with_groq(self, text_chunk, chunk_num, total_chunks, original_full_text):
        """Send a single text chunk to Groq for intelligent processing and basic factual check."""
        if not text_chunk or not text_chunk.strip():
            print(f"Skipping empty chunk {chunk_num}/{total_chunks}.")
            return ""

        detailed_prompt_instructions = """
        You are an expert document outliner. Analyze the provided text CHUNK and create a structured hierarchical outline.
        It is CRITICAL that you follow this specific formatting and indentation precisely:

        Example format:
        1. Main Topic One
        |-- Key point under Main Topic One
        | |-- Sub-point directly under the key point above
        |-- Another key point under Main Topic One
          1.b Subsection Title (indented under Main Topic One)
          |-- Key point under subsection 1.b
          | |-- Sub-point under the key point of subsection 1.b
          |-- Another key point under subsection 1.b
          1.c Another Subsection Title (indented similarly)
          |-- Point under 1.c
        2. Main Topic Two
        |-- 2.a Subsection Title for Main Topic Two (indented)
        | |-- Detail for 2.a
        |-- 2.b Another Subsection (indented)
        | |-- Detail for 2.b
        |-- Key point directly under Main Topic Two

        Formatting and Indentation Rules (MANDATORY):
        - Main sections: Start with a number and a period (e.g., "1. ", "2. "). No leading spaces.
        - Subsections: Start with the main section number, a letter, and a period (e.g., "1.b ", "2.a ").
          IMPORTANT: Subsections MUST be indented with exactly two (2) leading spaces before the number (e.g., "  1.b ").
        - Bullet points: Always start with "|-- " (pipe, two hyphens, space).
          - Bullets directly under a Main Section: The "|--" should have no additional leading spaces (i.e., aligns with Main Section text start).
          - Bullets directly under a Subsection: The "|--" should also have two (2) leading spaces to align with the Subsection's text. (e.g., "  |-- Key point under subsection 1.b").
        - Nested Bullet points (sub-bullets): For each additional level of nesting under a bullet, add two (2) more leading spaces before the "|--".
            Example of nested bullet indentation:
            1. Main Section
            |-- Level 1 Bullet (0 spaces before |--)
            | |-- Level 2 Bullet (2 spaces before |--)
            | | |-- Level 3 Bullet (4 spaces before |--)
              1.b Subsection (2 spaces before 1.b)
              |-- Level 1 Bullet under subsection (2 spaces before |--)
              | |-- Level 2 Bullet under subsection (4 spaces before |--)

        Please:
        1. Extract ALL meaningful information from THIS CHUNK of text.
        2. Organize it into a logical hierarchy following the rules above.
        3. Adhere strictly to the specified indentation for all elements.
        4. **ENSURE ALL FACTS ARE DIRECTLY SUPPORTED BY THE PROVIDED TEXT CHUNK. DO NOT INVENT OR HALLUCINATE INFORMATION.** If information is not in the text, do not include it.
        5. If citations like (Author, Year) are present in the text, include them naturally within the outline points.
        Preserve the original language of the text in the outline points as much as possible.

        Return ONLY the formatted outline for this chunk. Do not include any other text, greetings, or explanations.
        If this chunk is very short or doesn't contain outlineable content, return a minimal or empty outline.
        """

        chunk_context_prompt = f"This is Chunk {chunk_num} of {total_chunks} from a larger document.\nFocus on outlining the content within THIS CHUNK ONLY, following all formatting rules."

        messages = [
            {
                "role": "system",
                "content": "You are a highly precise document outlining assistant. Your sole task is to generate a hierarchical outline from the provided text chunk, strictly adhering to the user's detailed formatting and indentation rules. Output only the outline. Prioritize factual accuracy directly from the provided text."
            },
            {
                "role": "user",
                "content": f"{detailed_prompt_instructions}\n\n{chunk_context_prompt}\n\nHere is the text content for THIS CHUNK to analyze:\n\n---\n{text_chunk}\n---"
            }
        ]

        print(f"Sending Chunk {chunk_num}/{total_chunks} to Groq ({len(text_chunk)} chars)...")
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
                top_p=0.95,
                stream=False # Changed to False for full response before validation
            )
            outline_output = chat_completion.choices[0].message.content.strip()

            # Basic factual check: check if a significant portion of keywords from the outline exist in the original chunk
            # This is a rudimentary check, not a full factual verification.
            if self._basic_factual_check(outline_output, text_chunk):
                print(f"Chunk {chunk_num} outline passed basic factual check.")
                return outline_output
            else:
                print(f"Warning: Chunk {chunk_num} outline may contain inaccuracies. Skipping this chunk's outline.")
                return ""

        except Exception as e:
            print(f"Error with Groq API for Chunk {chunk_num}/{total_chunks}: {e}")
            return ""

    def _basic_factual_check(self, outline_text, original_chunk_text):
        """
        A very basic factual check: ensures that a reasonable percentage of non-common words
        from the generated outline are present in the original text chunk.
        This is not foolproof but helps catch obvious hallucinations.
        """
        if not outline_text or not original_chunk_text:
            return True # Nothing to check or source is empty

        outline_words = set(re.findall(r'\b\w+\b', outline_text.lower()))
        original_words = set(re.findall(r'\b\w+\b', original_chunk_text.lower()))

        common_words = {"a", "an", "the", "is", "are", "and", "or", "to", "of", "in", "for", "with", "on", "from", "at"}
        
        # Filter out common words
        significant_outline_words = [word for word in outline_words if word not in common_words]
        
        if not significant_outline_words:
            return True # No significant words to check, assume OK

        found_count = 0
        for word in significant_outline_words:
            if word in original_words:
                found_count += 1
        
        # Define a threshold, e.g., 70% of significant words should be found
        if len(significant_outline_words) > 0:
            match_percentage = (found_count / len(significant_outline_words)) * 100
            print(f"Factual check: {match_percentage:.2f}% of significant outline words found in original chunk.")
            return match_percentage >= 70
        return True # If no significant words in outline, assume it's fine (e.g., "1. Introduction")


    def parse_llm_outline(self, outline_text):
        """Parse the LLM's structured outline based on indentation."""
        if not outline_text: return []
        lines = outline_text.split('\n') 
        
        parsed_structure = []
        current_main_section = None
        current_subsection = None
        parent_bullet_stack = [] 

        for line_text in lines:
            stripped_line_content = line_text.strip()
            if not stripped_line_content: continue

            leading_spaces = len(line_text) - len(line_text.lstrip(' '))

            main_match = re.match(r'^(\d+\.\s+)(.*)', stripped_line_content)  # Capture marker and text separately
            if main_match and leading_spaces == 0:
                marker, title = main_match.groups()
                current_main_section = {'type': 'main_section', 'marker': marker.strip(), 'title': title.strip(), 'content': [], '_indent': 0}
                parsed_structure.append(current_main_section)
                current_subsection = None
                parent_bullet_stack = [(current_main_section, 0)] 
                continue

            subsection_match = re.match(r'^(\d+\.[a-zA-Z]\.\s+)(.*)', stripped_line_content)  # Capture marker and text
            if subsection_match and current_main_section and leading_spaces > 0 and not stripped_line_content.startswith('|--'):
                marker, title = subsection_match.groups()
                current_subsection = {'type': 'subsection', 'marker': marker.strip(), 'title': title.strip(), 'content': [], '_indent': leading_spaces}
                current_main_section['content'].append(current_subsection)
                while parent_bullet_stack and parent_bullet_stack[-1][1] >= leading_spaces:
                    parent_bullet_stack.pop() 
                parent_bullet_stack.append((current_subsection, leading_spaces))
                continue

            if stripped_line_content.startswith(BULLET_PREFIX):
                bullet_text = stripped_line_content[len(BULLET_PREFIX):].strip()
                
                active_parent_obj = None
                parent_expected_bullet_indent = 0
                
                for i in range(len(parent_bullet_stack) - 1, -1, -1):
                    p_obj, p_indent = parent_bullet_stack[i]
                    if leading_spaces >= p_indent:
                        active_parent_obj = p_obj
                        parent_expected_bullet_indent = p_indent
                        parent_bullet_stack = parent_bullet_stack[:i+1] 
                        break
                
                if not active_parent_obj: 
                    if parsed_structure: active_parent_obj = parsed_structure[-1] 
                    else: 
                        active_parent_obj = {'type': 'main_section', 'marker': '?', 'title': 'Orphaned Points', 'content': [], '_indent': 0}
                        parsed_structure.append(active_parent_obj)
                        parent_bullet_stack = [(active_parent_obj, 0)]
                    parent_expected_bullet_indent = active_parent_obj.get('_indent', 0)

                relative_indent_for_bullet = leading_spaces - parent_expected_bullet_indent
                bullet_level = 1 + (relative_indent_for_bullet // 2) 

                bullet_obj = {'type': 'bullet', 'text': bullet_text, 'level': bullet_level, '_abs_indent': leading_spaces}
                active_parent_obj['content'].append(bullet_obj)
                continue
        return parsed_structure

    def _render_content_recursive_docx(self, document, content_list, current_base_indent_inch):
        """Helper to recursively render content for DOCX, managing indentation and styling."""
        
        for item in content_list:
            item_type = item.get('type')
            
            if item_type == 'subsection':
                marker = item.get('marker', '')
                title = item.get('title', '')
                
                paragraph = document.add_paragraph()
                paragraph.paragraph_format.left_indent = current_base_indent_inch + Inches(0.25)
                paragraph.paragraph_format.space_before = Pt(6)
                paragraph.paragraph_format.space_after = Pt(6)
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

                # Add marker run
                marker_run = paragraph.add_run(f"{marker} ")
                marker_run.font.name = HIERARCHY_MARKER_FONT_NAME
                marker_run.font.size = Pt(HEADING_FONT_SIZE - 1) # Slightly smaller than main heading
                marker_run.bold = True
                
                # Add formatted title run with highlighting
                self._format_text_for_docx(paragraph, title, SUBTITLE_TEXT_FONT_NAME, DEFAULT_TEXT_COLOR, is_bold=True)
                
                self._render_content_recursive_docx(
                    document, 
                    item.get('content', []), 
                    current_base_indent_inch + Inches(0.25) 
                ) 
            
            elif item_type == 'bullet':
                text = item.get('text', '')
                bullet_level = item.get('level', 1) 
                
                paragraph = document.add_paragraph()
                bullet_indent_inch = current_base_indent_inch + (bullet_level - 1) * Inches(0.25)
                paragraph.paragraph_format.left_indent = bullet_indent_inch
                paragraph.paragraph_format.space_before = Pt(3)
                paragraph.paragraph_format.space_after = Pt(3)
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

                # Add bullet symbol run
                bullet_run = paragraph.add_run(f"{BULLET_PREFIX}")
                bullet_run.font.name = HIERARCHY_MARKER_FONT_NAME
                bullet_run.font.size = Pt(BODY_FONT_SIZE)
                bullet_run.bold = True

                # Add formatted text run with highlighting
                self._format_text_for_docx(paragraph, text, CONTENT_TEXT_FONT_NAME, DEFAULT_TEXT_COLOR)
                

    def create_docx_from_outline(self, parsed_structure, output_path):
        """Create a DOCX from the parsed outline structure with specified fonts and highlighting."""
        document = Document()

        # Set default font for the document (can be overridden by runs)
        # This part requires some direct XML manipulation for default font
        # The default font property is set on the document.styles[0].font
        document.styles['Normal'].font.name = 'Courier New'
        document.styles['Normal'].font.size = Pt(BODY_FONT_SIZE)

        main_section_base_indent_inch = Inches(0.25) # Base indent for main sections
        
        if not parsed_structure or (isinstance(parsed_structure, str) and not parsed_structure.strip()):
            paragraph = document.add_paragraph()
            paragraph.add_run("No structured content to generate DOCX.").font.size = Pt(BODY_FONT_SIZE)
            if isinstance(parsed_structure, str):
                paragraph = document.add_paragraph()
                self._format_text_for_docx(paragraph, parsed_structure, CONTENT_TEXT_FONT_NAME, DEFAULT_TEXT_COLOR)
        else:
            for main_section in parsed_structure:
                if main_section.get('type') == 'main_section':
                    marker = main_section.get('marker', '')
                    title = main_section.get('title', 'Untitled Section')

                    # Main Title Paragraph
                    paragraph = document.add_paragraph()
                    paragraph.paragraph_format.left_indent = main_section_base_indent_inch
                    paragraph.paragraph_format.space_before = Pt(12) # Spacing before main heading
                    paragraph.paragraph_format.space_after = Pt(8)  # Spacing after main heading
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

                    # Add marker run
                    marker_run = paragraph.add_run(f"{marker} ")
                    marker_run.font.name = HIERARCHY_MARKER_FONT_NAME
                    marker_run.font.size = Pt(HEADING_FONT_SIZE)
                    marker_run.bold = True
                    
                    # Add formatted title run with highlighting
                    self._format_text_for_docx(paragraph, title, TITLE_TEXT_FONT_NAME, DEFAULT_TEXT_COLOR, is_bold=True)

                    # Recursively render content
                    self._render_content_recursive_docx(
                        document, 
                        main_section.get('content', []), 
                        main_section_base_indent_inch
                    )
                document.add_paragraph().add_run().add_break() # Add a line break after each main section for spacing

        try:
            document.save(output_path)
            print(f"DOCX created successfully: {output_path}")
        except Exception as e:
            print(f"Error creating DOCX: {e}")

    def process_file(self, input_path, output_path=None):
        print(f"Processing PDF: {input_path}")
        file_ext = os.path.splitext(input_path)[1].lower()
        if file_ext != '.pdf':
            print(f"Unsupported file type: {file_ext}.")
            return None

        pdf_full_text = self.extract_text_from_pdf(input_path)
        if not pdf_full_text:
            print("Failed to extract text from PDF.")
            return None

        text_chunks = self.split_text_into_chunks(pdf_full_text)
        if not text_chunks:
            print("PDF text resulted in no processable chunks.")
            return None
            
        print(f"PDF text split into {len(text_chunks)} chunks.")
        all_outlines = []
        for i, chunk_text in enumerate(text_chunks):
            print(f"\nProcessing Chunk {i+1} of {len(text_chunks)}")
            # Pass original_full_text for potential factual checking
            chunk_outline = self.process_with_groq(chunk_text, i + 1, len(text_chunks), pdf_full_text) 
            if chunk_outline:
                all_outlines.append(chunk_outline)
            else:
                print(f"Chunk {i+1} did not yield an outline or failed factual check.")
        
        if not all_outlines:
            print("No outlines were generated from any chunks.")
            return None

        combined_outline_text = "\n".join(all_outlines) 

        print("\n--- Combined Outline from All Chunks ---")
        print(combined_outline_text)
        print("--- End of Combined Outline ---")

        parsed_structure = self.parse_llm_outline(combined_outline_text)
        
        if not output_path:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = f"{base_name}_groq_styled_outline.docx" # Changed extension to .docx

        if not parsed_structure:
            print("Failed to parse the combined outline into a structured format. DOCX will contain raw combined text.")
            # Pass the raw combined_outline_text if parsing fails.
            self.create_docx_from_outline(combined_outline_text, output_path)
        else:
            self.create_docx_from_outline(parsed_structure, output_path)
        
        return output_path

def main():
    print("Groq-Powered Outline Converter (Styled DOCX Output)")
    print("=" * 60)
    print("Note: This script converts outlines to DOCX, preserving color and structure.")
    print("Factual checking is rudimentary (keyword presence). For critical use, human review is essential.")
    print("-" * 60)

    api_key_input = input("Enter your Groq API key (or press Enter if GROQ_API_KEY env var is set): ").strip()
    groq_api_key = api_key_input if api_key_input else os.environ.get('GROQ_API_KEY')
    if not groq_api_key:
        print("Groq API key not found.")
        return

    try:
        converter = GroqOutlineConverter(api_key=groq_api_key)
    except Exception:
        print("Exiting due to converter initialization failure.")
        return

    input_file = ""
    while True:
        input_file = input("Enter path to your PDF file: ").strip()
        if not input_file:
            print("No input file provided. Exiting.")
            return
        if not os.path.exists(input_file):
            print(f"Error: File not found: '{input_file}'")
        elif not input_file.lower().endswith(".pdf"):
            print("Error: This script supports PDF files only.")
        else:
            break
    
    output_file_input = input("Enter output DOCX path (press Enter for auto-naming): ").strip()
    output_docx_path = output_file_input if output_file_input else None

    try:
        result = converter.process_file(input_file, output_docx_path)
        if result:
            print(f"\nSuccess! Styled Outline DOCX saved to: {result}")
        else:
            print("\nProcessing failed to produce an output DOCX.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
