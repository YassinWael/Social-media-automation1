import logging
from icecream import ic
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from json import loads
from os import environ
load_dotenv()


genai_api_key = environ.get("genai_api_key")
unsplash_key = environ.get("unsplash_access_key")

def upload_image_to_facebook(page_id, page_token,image_url):
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
        return upload["id"]
    else:
        ic(f"Error uploading image: {upload}")
        return None
    

def get_image_from_unsplash(query="fancy black"):
    """
    Get a random image from Unsplash based on the query.
    """
  
    logging.info("Unsplash API called.")
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
        ic(f"Image URL from Unsplash: {image_url}")
        return image_url
    else:
        ic(f"Error fetching image from Unsplash: {response.status_code} - {response.text}")
        return None

def query_gemini(prompt,text="",scheme=""):
    genai.configure(api_key=genai_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    JSON_ONLY = f"ONLY RETURN THE RESULT AS JSON, Make sure the json will NOT raise a JSONDecodeError when loaded with json.loads() in Python. You should make sure your json doesn't violate the scheme: {str(scheme)}, if unable to fill a value in the scheme simply leave it as None"
    try:
        response = model.generate_content(f"{prompt}, {JSON_ONLY}:  {text}")
        json_content = response.text.lstrip("```json\n").rstrip("```")
        print(json_content)
        ic(loads(json_content))
        return loads(json_content)
    except Exception as e:
        ic(f"Error in query_gemini: {e}")
        return scheme if isinstance(scheme, dict) else {}
        


def get_page_token(page_id,session):
    """
    Get the page access token for a given page ID.
    This is used to post to the page.
    """
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
        return response.json().get("access_token")
    return None
