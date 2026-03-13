import base64
import json
import requests
import io
import os
import os
import streamlit as st
from PIL import Image
from openai import OpenAI

# ==========================================
# 🔐 CONFIGURATION
# ==========================================
# Look for keys in Streamlit secrets first, fallback to environment variables
API_KEY = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
UNSPLASH_API_KEY = st.secrets.get("UNSPLASH_API_KEY", os.environ.get("UNSPLASH_API_KEY", ""))

if not API_KEY:
    print("WARNING: OPENAI_API_KEY is not set.")

client = OpenAI(api_key=API_KEY) if API_KEY else None

# ==========================================
# 🧠 THE "PRODUCTION BIBLE" PROMPT
# ==========================================
SYSTEM_PROMPT = """
You are the Head of Production for a massive e-commerce shoot. 
I am sending you a Moodboard that contains MULTIPLE visual directions (e.g., Pastel Studio, Dark Tech, Lifestyle, Monochrome Green).

Your goal is to write a **Comprehensive Production Bible**. Do not summarize. Be exhaustive. 
You must break down the requirements into these exact 5 Major Categories, and inside them, identify specific sub-themes found in the image.

### REQUIRED STRUCTURE (JSON):
You must return a JSON object with a key "categories". 
Inside "categories", create a list where each entry has:
- "title": (e.g., "1. SURFACES & BACKGROUNDS")
- "subsections": A list of specific visual themes found in the image.
    - "name": (e.g., "A. Soft Pastel Setup", "B. Dark Tech Environment")
    - "items": A list of distinct items.
        - "name": (e.g., "Savage Universal Seamless Paper - Baby Pink")
        - "note": (e.g., "For the colorful cable shots")
        - "price": (Estimated INR cost)
        - "source": ("Buy", "Rent", "Office Inventory")

### 📝 CONTENT REQUIREMENTS (BE OBSESSIVE):
1. **SURFACES:** Differentiate between Matte Paper, Acrylic Sheets, Vinyl, and Textured Walls.
2. **PROPS:** List every specific device (MacBook, iPhone), decor (Plants, Mugs), and Styling Prop (Acrylic blocks, Risers).
3. **RIGGING (The Invisible Tools):** You MUST list the tools needed to fake the physics (Fishing line, Armature wire, Glue dots, C-Stands).
4. **LIGHTING:** Differentiate between Soft (Pastel) vs Hard/Rim (Dark Tech) lighting requirements.
5. **MODELS:** Detailed demographics (Age, Gender, Skin Tone, Hands) and Animals (Breed, Color).

### EXAMPLE JSON OUTPUT:
{
  "categories": [
    {
      "title": "1. SURFACES & BACKGROUNDS",
      "subsections": [
        {
          "name": "A. Soft Pastel Setups",
          "items": [
            {"name": "Savage Universal Seamless Paper - Baby Pink", "note": "Matte finish", "price": 4500, "source": "Buy"},
            {"name": "Matte Acrylic Sheet - Soft Mint", "note": "For reflective floor", "price": 2000, "source": "Buy"}
          ]
        },
        {
          "name": "B. Dark Tech Environment",
          "items": [
            {"name": "Matte Black Vinyl Sheet", "note": "Non-reflective base", "price": 1200, "source": "Buy"}
          ]
        }
      ]
    }
  ]
}
"""

def encode_image(image_source):
    # Check if it's a Streamlit uploaded file (has a getvalue() method)
    if hasattr(image_source, 'getvalue'):
        return base64.b64encode(image_source.getvalue()).decode("utf-8")
    # Otherwise assume it's a file path string
    elif isinstance(image_source, str) and os.path.exists(image_source):
        with open(image_source, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    else:
        raise ValueError("Invalid image source provided.")

def fetch_unsplash_images(query, count=4):
    """Fetches high-quality images from Unsplash API."""
    if not UNSPLASH_API_KEY:
        return {"error": "Unsplash API key is missing. Please add it to backend.py."}
    
    url = f"https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {UNSPLASH_API_KEY}"}
    params = {
        "query": query,
        "per_page": count,
        "orientation": "landscape"
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        if not results:
            return {"error": "No images found for that query."}
        
        # Extract the regular-sized image URLs
        image_urls = [img["urls"]["regular"] for img in results]
        return image_urls
    else:
        return {"error": f"Failed to fetch images from Unsplash. Status code: {response.status_code}. Response: {response.text}"}

def create_collage(image_urls, output_filename="generated_moodboards/temp_moodboard.jpg"):
    """Downloads images and stitches them into a 2x2 grid."""
    images = []
    
    if not os.path.exists("generated_moodboards"):
        os.makedirs("generated_moodboards")
        
    for url in image_urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                # Standardize size before pasting
                img = img.resize((800, 600), Image.LANCZOS)
                images.append(img)
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            
    if not images:
        return {"error": "Could not download any images."}
        
    # We aim for a 2x2 grid (assuming we get 4 images)
    # If we get less than 4, we just use what we have in a row/column as best effort
    grid_width = 800 * 2
    grid_height = 600 * 2
    
    # Create the blank canvas
    collage = Image.new('RGB', (grid_width, grid_height), (255, 255, 255))
    
    positions = [
        (0, 0),         # Top left
        (800, 0),       # Top right
        (0, 600),       # Bottom left
        (800, 600)      # Bottom right
    ]
    
    for i, img in enumerate(images):
        if i < 4:
            collage.paste(img, positions[i])
            
    collage.save(output_filename)
    return output_filename

def generate_ai_moodboard(query):
    """Wrapper function to handle fetching and collaging."""
    result = fetch_unsplash_images(query, count=4)
    
    # Check if an error dict was returned
    if isinstance(result, dict) and "error" in result:
        return result
        
    # Otherwise result is a list of URLs
    return create_collage(result)

def analyze_moodboard(image_source):
    if not client:
        return {"error": "OpenAI API key is missing. Please add it to your secrets or environment variables."}
        
    base64_image = encode_image(image_source)

    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Create the exhaustive Production Bible from this moodboard. Separate every visual theme (Pastel, Green, Dark, Lifestyle). List EVERY prop and tool required."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.2, # Keep it strict and structured
            max_tokens=4096  # Max length to ensure the list is long
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        return data

    except Exception as e:
        return {"error": str(e)}