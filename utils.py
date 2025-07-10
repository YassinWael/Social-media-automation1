import logging
import re
from icecream import ic
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from json import loads
from os import environ
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
from os import path
import time
load_dotenv()
#

genai_api_key = environ.get("genai_api_key")
unsplash_key = environ.get("unsplash_access_key")
image_upload_key = environ.get("image_upload_key")
if not all([genai_api_key,unsplash_key,image_upload_key]):
    logging.warning(f"One of the api keys is empty: {genai_api_key,unsplash_key,image_upload_key}")
def upload_image_to_facebook(page_id, page_token,image_url):
    logging.info(f"Uploading: {image_url}...")
    start_time = time.time()
    upload = requests.post(
        f"https://graph.facebook.com/v23.0/{page_id}/photos",
        params= {
            "access_token":page_token,
            "url":image_url,
            "published":"false"
        }
    ).json()
    ic(f"Uploaded image to facebook: {upload}")
    if "id" in upload:
        logging.info(f"Uploaded image to facebook in {time.time() - start_time:.2f}")
        return upload["id"]
    else:
        ic(f"Error uploading image: {upload}")
        return None
    

def get_image_from_unsplash(query="fancy black"):
    """
    Get a random image from Unsplash based on the query.
    """
  
    logging.info(f"Unsplash API called, with query {query}")
    response = requests.get(
    f"https://api.unsplash.com/search/photos",
    params={
        "query":query,
        "per_page":1,
        "client_id":unsplash_key
        }
)
    if response.status_code == 200:
        print(response.json()['results'][0]['urls']['regular'])
        image_url = response.json()['results'][0]['urls']['regular']
        logging.info(f"Image URL from Unsplash: {image_url}")
        return image_url
    else:
        ic(f"Error fetching image from Unsplash: {response.status_code} - {response.text}")
        return None

def query_gemini(prompt,text="",image_path="",scheme=""):
    start_time = time.time()
    genai.configure(api_key=genai_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    JSON_ONLY = f"ONLY RETURN THE RESULT AS JSON, Make sure the json will NOT raise a JSONDecodeError when loaded with json.loads() in Python. use double quotes for property names. You should make sure your json doesn't violate the scheme: {str(scheme)}, if unable to fill a value in the scheme simply leave it as None"
    try:
        response = model.generate_content([f"{prompt}, {JSON_ONLY}:  {text}",Image.open(image_path)] if image_path else f"{prompt}, {JSON_ONLY}:  {text}")
        raw_text = response.text
        match = re.search(r"\{.*\}",raw_text,re.DOTALL)
        if not match:
            raise ValueError("No JSON found in response")
        json_content = match.group(0)

        print(json_content)
        logging.info(f"Received response from gemini: {json_content}")
        ic(loads(json_content))
        if isinstance(json_content,list):
            json_content = json_content[0]
        logging.info(f"Time taken to query gemini: {time.time() - start_time:.2f} seconds")
        return loads(json_content)
    except Exception as e:
        logging.error(f"Error with gemini api: {e}")
        ic(f"Error in query_gemini: {e}")
        return scheme if isinstance(scheme, dict) else {}
        


def get_page_token(page_id,session):
    """
    Get the page access token for a given page ID.
    This is used to post to the page.
    """
    logging.info(f"Getting token for: {page_id}")
    user_token = session.get("user_token")
    if not user_token:
        return None
    response = requests.get(
        f"https://graph.facebook.com/v23.0/{page_id}",
        params={
            "fields": "access_token",
            "access_token": user_token
        }
    )
    if response.status_code == 200:
        ic(response.json())
        logging.info(f"Token Response: {response.json()}")
        return response.json().get("access_token")
    return None






def add_text_to_image(image_path, text, output_path='output.png'):
    """
    Adds a clean, wrapped text overlay to an image.
    Chooses a moderate font size so it remains legible without overwhelming the image.
    Returns the path to the saved output image.
    """
    logging.info(f"Adding {text} to {image_path}...")
    # Open image and create transparent overlay
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Base font size: 6% of image height, bounded between 18 and 40 px
    base_size = int(height * 0.06)
    font_size = max(18, min(base_size, 40))

    # Attempt to load a common TrueType font
    font_candidates = [
        "DejaVuSans-Bold.ttf", "DejaVuSans.ttf",
        "FreeSans.ttf", "LiberationSans-Regular.ttf"
    ]
    font = None
    bundled_font_path = path.join(path.dirname(__file__),"fonts","arial.ttf")
    try:
        font = ImageFont.truetype(bundled_font_path, font_size)
        ic(f"Loaded Arial: {bundled_font_path}")
    except Exception as e:
        for fname in font_candidates:
            try:
                font = ImageFont.truetype(fname, font_size)
                ic(f"Loaded font: {fname}")
                break
            except OSError:
                continue
   
    if font is None:
        font = ImageFont.load_default()
    
    # Function to measure text size
    def _text_size(s, f):
        try:
            bbox = draw.textbbox((0, 0), s, font=f)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            return f.getsize(s)

    # Wrap text to fit within 85% of image width
    max_w = width * 0.85
    avg_char_w, _ = _text_size("A", font)
    wrap_chars = max(int(max_w / (avg_char_w or 1)), 40)
    lines = textwrap.wrap(text, width=wrap_chars)

    # Calculate block dimensions
    line_h = _text_size("A", font)[1]
    spacing = int(line_h * 0.15)
    block_h = line_h * len(lines) + spacing * (len(lines) - 1)
    block_w = max(_text_size(line, font)[0] for line in lines)

    # Position: center horizontally, 8% from bottom
    x = (width - block_w) / 2
    y = height - block_h - (height * 0.08)

    # Draw semi-transparent background rectangle
    pad = int(font_size * 0.3)
    rect = [x - pad, y - pad, x + block_w + pad, y + block_h + pad]
    draw.rectangle(rect, fill=(0, 0, 0, 140))

    # Draw each text line
    for idx, line in enumerate(lines):
        draw.text((x, y + idx * (line_h + spacing)), line, font=font, fill=(255, 255, 255, 255))

    # Composite and save
    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(output_path, format='PNG')
    return output_path


def upload_image(image_path="",file_data=""):
    """Uploads an image to catbox.me and returns the image's display URL
    
    Args:
        image_path (str): Path to the image file to upload.
    
    Returns:
        str: The URL of the uploaded image.
    """
    url = "https://catbox.moe/user/api.php"
    if not any([image_path,file_data]): return None
    
    start_time = time.time()
    logging.info(f"Uploading {image_path}...") if image_path else logging.info(f"Uploading file_data...")
    if image_path:
        with open(image_path,"rb") as f:
            response = requests.post(
                url = url,
                data= {
                    "reqtype":'fileupload'
                },
                files={
                    "fileToUpload":f
                }
            )
    else:
        response = requests.post(
            url = url,
            data = {
                "reqtype":'fileupload'
            },
            files = {
                "fileToUpload":file_data
            }
        )
    logging.info(f"Uploaded to: {response.text} in {time.time() - start_time:.2f} seconds. ")
    return response.text
