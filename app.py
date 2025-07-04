from pprint import pprint
from flask import Flask, redirect, request, session, url_for, render_template
import os
import requests
from dotenv import load_dotenv
from icecream import ic
from utils import *
from json import loads,dumps
import logging

# Set up logging to both console and file
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'app.log'

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)


logging.basicConfig(level=logging.INFO, handlers=[file_handler])

flask_logger = logging.getLogger('werkzeug')
flask_logger.setLevel(logging.ERROR)




load_dotenv()  # pull in .env vars
app = Flask(__name__)
app.secret_key = "desfjofisjfsnoifjes"  # session encryption (dev-only) in prod use a fixed key

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
REDIRECT_URI = "https://f762-213-137-138-220.ngrok-free.app/callback"


# --- 1. Home page ---
@app.route("/")
def index():
    # session.clear()
    return render_template("index.html")


# --- 2. Kick off OAuth ---
@app.route("/login")
def login():
    scopes = (
        "pages_manage_posts,"  # publish to Pages
        "pages_read_engagement,"  # read likes/comments
        "pages_show_list,"  # list user Pages
    )
    auth_url = (
        f"https://www.facebook.com/v23.0/dialog/oauth?"
        f"client_id={FB_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes}"
    )
    return redirect(auth_url)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# --- 3. OAuth callback ---
@app.route("/callback")
def callback():
    # Facebook sends ?code=xxxx
    code = request.args.get("code")
    if not code:
        return "Login failed – no code parameter!", 400
    ic(code)
    # Exchange code → user access token
    token_resp = requests.get(
        "https://graph.facebook.com/v23.0/oauth/access_token",
        params={
            "client_id": FB_APP_ID,
            "redirect_uri": REDIRECT_URI,
            "client_secret": FB_APP_SECRET,
            "code": code,
        },
        timeout=10,
    ).json()
    print("----------------------------------------------------------------------")
    ic(token_resp)
    print("----------------------------------------------------------------------")
    session["user_token"] = token_resp["access_token"]
    user_info = requests.get(
        "https://graph.facebook.com/v23.0/me",
        params = {
            "access_token": session["user_token"],
            "fields": "id,name,email"
        }
    ).json()
    ic(user_info)
    logging.info(f"User ({user_info['name']}) logged in with token: {session['user_token']}")
    return redirect("/pages")


# --- 4. Quick debug route: show the scopes we actually got ---
@app.route("/debug")
def debug():
    user_token = session.get("user_token")
    if not user_token:
        return "Login first!", 401

    perms = requests.get(
        "https://graph.facebook.com/v23.0/me/permissions",
        params={"access_token": user_token},
        timeout=10,
    ).json()
    return perms  # Flask will jsonify the dict


@app.route("/pages")
def pages():
    user_token = session.get("user_token")
    if not user_token:
        return redirect("/login")

    response = requests.get(
        "https://graph.facebook.com/v23.0/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,name,access_token,tasks"
        }
    )
    ic(response.status_code)
    pages = response.json().get("data", [])
    return render_template("pages.html", pages=pages)


@app.route("/post/<page_id>", methods=["POST"])
def post_to_page(page_id):
    user_token = session.get("user_token")
    page_token = get_page_token(page_id, session)
    message = request.form.get("message")

    if not user_token or not page_token or not message:
        return redirect("/login")

    # image_id = upload_image_to_facebook(page_id, page_token, request.form.get("image_url"))

    response = requests.post(
        f"https://graph.facebook.com/v23.0/{page_id}/feed",
        params={
            "access_token": page_token,
            "message": message
            # "attached_media":dumps([{"media_fbid":image_id}])
        }
    )
    ic(response.status_code)
    return redirect(url_for('posts', page_id=page_id))


@app.route('/posts/<page_id>')
def posts(page_id):
    user_token = session.get("user_token")
    if not user_token:
        return redirect("/login")

    page_token = get_page_token(page_id, session)
    if not page_token:
        return "Could not retrieve page token", 400
        
    page_details_resp = requests.get(
        f"https://graph.facebook.com/v23.0/{page_id}",
        params={"access_token": page_token, "fields": "name"}
    )
    page_name = page_details_resp.json().get("name", "")


    response = requests.get(
        f"https://graph.facebook.com/v23.0/{page_id}/published_posts",
        params={
            "access_token": page_token,
            "fields": "id,message,created_time,permalink_url",
        }
    )

    ic(response.status_code)
    posts_data = response.json().get("data", [])
    list_of_post_ids = [post['id'] for post in posts_data]
    ic(posts_data,list_of_post_ids)
    print("----------------------------------")

    image = session.get(f"image_{page_id}")
    posts_niche = session.get(f"posts_niche_{page_id}")
    if not posts_niche or session.get('post_ids',[]) != list_of_post_ids: # new post or something similar
        posts_niche = query_gemini(
            prompt="Extract the niche of the facebook page that's posting these posts, ONLY THREE WORDS MAX AS THE NICHE",
            text=str(posts_data),
            scheme={'niche': None}
        ).get('niche', 'General')
        image = get_image_from_unsplash(posts_niche)
        session[f"posts_niche_{page_id}"] = posts_niche
        session[f'image_{page_id}']= image
    else:
        ic(f"Using cached niche for {page_id}: {posts_niche}")
    if not image:
        image = get_image_from_unsplash(posts_niche)
        session[f'image_{page_id}']= image


    session['post_ids'] = list_of_post_ids

    return render_template("posts.html", posts=posts_data, niche=posts_niche, image=image, page_id=page_id, page_name=page_name)

@app.route('/generate_posts/<page_id>', methods=["POST"])
def generate_posts(page_id):
    pass
if __name__ == "__main__":
    app.run(debug=True, port=5000)