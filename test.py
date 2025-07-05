from dotenv import load_dotenv
from os import environ
from requests import get


load_dotenv()  # pull in .env vars
unsplash_key = environ.get("unsplash_access_key")

response = get(
    f"https://api.unsplash.com/search/photos",
    params={
        "query":"Dog",
        "per_page":1,
        "client_id":unsplash_key
        }
)
print(response.json()['results'][0]['urls']['regular'])