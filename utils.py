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



def add_text_to_image(image_path, text="Money is life.", output_path="output.png"):
    """
    Add a glass-like effect and a blurred background to a given image, with
    a message on top of it. The text is wrapped and its size is adjusted to fit
    within the glass area. The output image is saved to a file.

    Args:
        image_path (str): path to the input image
        text (str, optional): text to display on top of the image. Defaults to "Money is life."
        output_path (str, optional): path to the output image. Defaults to "output.png"

    Returns:
        str: path to the output image
    """
    start_time = time.time()
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # Background blur area
    fade_height = int(height * 0.25)
    blur_y_start = height - fade_height
    blur_box = (0, blur_y_start, width, height)
    blurred_region = img.crop(blur_box).filter(ImageFilter.GaussianBlur(radius=10))
    img.paste(blurred_region, blur_box)

    # Overlay with glass effect
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin_x = int(width * 0.05)
    margin_y = int(fade_height * 0.15)
    rect_shape = [margin_x, blur_y_start + margin_y, width - margin_x, height - margin_y]
    draw.rounded_rectangle(rect_shape, radius=30, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, overlay)

    # Draw wrapped text
    draw = ImageDraw.Draw(img)
    max_width = rect_shape[2] - rect_shape[0] - 20  # padding inside the box

    font_size = int(fade_height * 0.3)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Wrap and shrink if needed
    wrapper = textwrap.TextWrapper(width=40)
    while True:
        lines = wrapper.wrap(text)
        try:
            line_widths = [draw.textlength(line, font=font) for line in lines]
        except:
            line_widths = [draw.textsize(line, font=font)[0] for line in lines]
        if max(line_widths) <= max_width or font_size <= 10:
            break
        font_size -= 2
        font = ImageFont.truetype("arial.ttf", font_size)

    # Calculate total text height
    total_text_height = 0
    line_heights = []
    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
        except:
            line_height = draw.textsize(line, font=font)[1]
        line_heights.append(line_height)
        total_text_height += line_height + 10  # 10 px spacing

    start_y = blur_y_start + (fade_height - total_text_height) // 2

    for i, line in enumerate(lines):
        try:
            line_width = draw.textlength(line, font=font)
        except:
            line_width = draw.textsize(line, font=font)[0]
        x = (width - line_width) // 2
        draw.text((x, start_y), line, font=font, fill=(255, 255, 255, 255))
        start_y += line_heights[i] + 10

    img.convert("RGB").save(output_path)
    logging.info(f"Image saved to {output_path} in {time.time() - start_time:.2f} seconds")
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
