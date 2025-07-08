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
    JSON_ONLY = f"ONLY RETURN THE RESULT AS JSON, Make sure the json will NOT raise a JSONDecodeError when loaded with json.loads() in Python. DOUBLE QUOTES You should make sure your json doesn't violate the scheme: {str(scheme)}, if unable to fill a value in the scheme simply leave it as None"
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


def add_text_to_image(
    image_path,
    text="Money is life.",
    output_path="output.png",
    blur_radius=15,
    glass_color=(255, 255, 255, 70),
    border_color=(255, 255, 255, 100),
    border_width=2,
    text_color=(255, 255, 255, 245),
    shadow_color=(0, 0, 0, 110)
):
    start_time = time.time()
    try:
        img = Image.open(image_path).convert("RGBA")
    except FileNotFoundError:
        logging.error(f"Error: Input image not found at {image_path}")
        return None

    width, height = img.size

    # 1. Background Blur
    blur_area_height = int(height * 0.25)
    blur_y_start = height - blur_area_height
    blur_box = (0, blur_y_start, width, height)
    blurred_region = img.crop(blur_box).filter(ImageFilter.GaussianBlur(radius=blur_radius))
    img.paste(blurred_region, blur_box)

    # 2. Frosted glass panel coords
    margin_x = int(width * 0.05)
    margin_y = int(blur_area_height * 0.15)
    rect_x1 = margin_x
    rect_y1 = blur_y_start + margin_y
    rect_x2 = width - margin_x
    rect_y2 = height - margin_y

    # Frosted Glass Overlay
    glass_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glass_overlay)
    draw.rounded_rectangle(
        [rect_x1 - border_width, rect_y1 - border_width, rect_x2 + border_width, rect_y2 + border_width],
        radius=30 + border_width,
        fill=border_color
    )
    draw.rounded_rectangle([rect_x1, rect_y1, rect_x2, rect_y2], radius=30, fill=glass_color)
    img = Image.alpha_composite(img, glass_overlay)

    # 3. TrueType font loader
    def get_truetype_font(size):
        candidates = [
            "arial.ttf",                                    # Windows
            "/Library/Fonts/Arial.ttf",                     # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Linux
        ]
        for fp in candidates:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
        raise RuntimeError("No TrueType font found. Install one or update the path.")

    draw = ImageDraw.Draw(img)
    padding = int(margin_x * 0.5)
    max_w = rect_x2 - rect_x1 - padding * 2
    max_h = rect_y2 - rect_y1 - padding * 2

    # 4. Binary search for largest fitting font size
    lo, hi = 10, max(max_w, max_h)
    best_size = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font = get_truetype_font(mid)

        # wrap text
        words = text.split()
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textlength(test, font=font) <= max_w:
                line = test
            else:
                lines.append(line)
                line = w
        lines.append(line)

        # calc total height via textbbox
        line_heights = [
            draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1]
            for l in lines
        ]
        total_h = sum(line_heights) + (len(lines) - 1) * (mid // 5)

        if total_h <= max_h:
            best_size, lo = mid, mid + 1
        else:
            hi = mid - 1

    # 5. Render final text
    font = get_truetype_font(best_size)
    words = text.split()
    final_lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            line = test
        else:
            final_lines.append(line)
            line = w
    final_lines.append(line)

    line_heights = [
        draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1]
        for l in final_lines
    ]
    total_h = sum(line_heights) + (len(final_lines) - 1) * (best_size // 5)
    y = rect_y1 + (rect_y2 - rect_y1 - total_h) / 2

    for l, h in zip(final_lines, line_heights):
        w_text = draw.textlength(l, font=font)
        x = rect_x1 + (rect_x2 - rect_x1 - w_text) / 2
        # shadow
        draw.text((x + 2, y + 2), l, font=font, fill=shadow_color)
        # main text
        draw.text((x, y), l, font=font, fill=text_color)
        y += h + best_size // 5

    img.convert("RGB").save(output_path)
    logging.info(f"Image saved to {output_path} in {time.time() - start_time:.2f}s")
    return output_path


add_text_to_image("image.png","Buy this buy this car watch those whddgeels buy thi..s")

def upload_image(image_path):
    """Uploads an image to catbox.me and returns the image's display URL
    
    Args:
        image_path (str): Path to the image file to upload.
    
    Returns:
        str: The URL of the uploaded image.
    """
    start_time = time.time()
    logging.info(f"Uploading {image_path}...")
    with open(image_path,"rb") as f:
        response = requests.post(
            url = "https://catbox.moe/user/api.php",
            data= {
                "reqtype":'fileupload'
            },
            files={
                "fileToUpload":f
            }
        )
    logging.info(f"Uploaded to: {response.text} in {time.time() - start_time:.2f} seconds. ")
    return response.text
