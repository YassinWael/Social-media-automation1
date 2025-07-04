from icecream import ic
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from os import environ
load_dotenv()


genai_api_key = environ.get("genai_api_key")

def query_gemini(prompt,text="",scheme=""):
    model = genai.GenerativeModel("gemini-2.0-flash")
    JSON_ONLY = f"ONLY RETURN THE RESULT AS JSON, Make sure the json will NOT raise a JSONDecodeError when loaded with json.loads() in Python. You should make sure your json doesn't violate the scheme: {scheme}"
    try:
        response = """"""
    except Exception as e:
        ic(f"Error in query_gemini: {e}")
        return None
        






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
