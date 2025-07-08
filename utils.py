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

    w, h = img.size

    # 1. Background blur
    blur_h = int(h * 0.25)
    blur_y = h - blur_h
    region = img.crop((0, blur_y, w, h)).filter(ImageFilter.GaussianBlur(blur_radius))
    img.paste(region, (0, blur_y))

    # 2. Frosted glass panel
    margin_x = int(w * 0.05)
    margin_y = int(blur_h * 0.15)
    x1, y1 = margin_x, blur_y + margin_y
    x2, y2 = w - margin_x, h - margin_y

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # border
    d.rounded_rectangle(
        [x1 - border_width, y1 - border_width, x2 + border_width, y2 + border_width],
        radius=30 + border_width,
        fill=border_color
    )
    # glass
    d.rounded_rectangle([x1, y1, x2, y2], radius=30, fill=glass_color)
    img = Image.alpha_composite(img, overlay)

    # 3. Prepare default bitmap font
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(img)

    # compute text‐box for scaling
    pad = int(margin_x * 0.5)
    box_w = (x2 - x1) - pad * 2
    box_h = (y2 - y1) - pad * 2

    # wrap into lines at default font
    words = text.split()
    lines, cur = [], ""
    for wrd in words:
        test = (cur + " " + wrd).strip()
        if draw.textlength(test, font=font) <= box_w:
            cur = test
        else:
            lines.append(cur)
            cur = wrd
    lines.append(cur)

    # measure original text size
    line_spacing = 4
    orig_w = 0
    heights = []
    for L in lines:
        bbox = draw.textbbox((0, 0), L, font=font)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        orig_w = max(orig_w, lw)
        heights.append(lh)
    orig_h = sum(heights) + (len(lines) - 1) * line_spacing

    # scale factor
    sf = min(box_w / orig_w, box_h / orig_h)
    new_w = max(1, int(orig_w * sf))
    new_h = max(1, int(orig_h * sf))

    # render text at default size into small layer
    text_layer = Image.new("RGBA", (orig_w, orig_h), (0, 0, 0, 0))
    dt = ImageDraw.Draw(text_layer)
    yy = 0
    for L, lh in zip(lines, heights):
        dt.text((0, yy), L, font=font, fill=(255,255,255,255))
        yy += lh + line_spacing

    # scale it up
    scaled = text_layer.resize((new_w, new_h), resample=Image.LANCZOS)
    mask = scaled.split()[3]

    # calculate paste position
    dest_x = x1 + pad + ((box_w - new_w) // 2)
    dest_y = y1 + pad + ((box_h - new_h) // 2)

    # draw shadow
    shadow_off = max(1, int(2 * sf))
    shadow_img = Image.new("RGBA", (new_w, new_h), shadow_color)
    shadow_img.putalpha(mask)
    img.paste(shadow_img, (dest_x + shadow_off, dest_y + shadow_off), shadow_img)

    # draw main text
    text_img = Image.new("RGBA", (new_w, new_h), text_color)
    text_img.putalpha(mask)
    img.paste(text_img, (dest_x, dest_y), text_img)

    # save
    img.convert("RGB").save(output_path)
    logging.info(f"Image saved to {output_path} in {time.time() - start_time:.2f}s")
    return output_path



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
