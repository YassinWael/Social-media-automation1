from flask import Flask, redirect, request, session, url_for, render_template
import os, requests
from dotenv import load_dotenv
from icecream import ic
from utils import *
# --- 0. Bootstrapping ---
load_dotenv()                 # pull in .env vars
app = Flask(__name__)
app.secret_key = os.urandom(24)  # session encryption (dev-only)

FB_APP_ID     = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
REDIRECT_URI  = "http://localhost:5000/callback"



# --- 1. Home page ---
@app.route("/")
def index():
    return render_template("index.html")

# --- 2. Kick off OAuth ---
@app.route("/login")
def login():
    scopes = (
        "pages_manage_posts,"      # publish to Pages
        "pages_read_engagement,"   # read likes/comments
        "pages_show_list,"          # list user Pages
    )
    auth_url = (
        f"https://www.facebook.com/v23.0/dialog/oauth?"
        f"client_id={FB_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes}"
    )
    return redirect(auth_url)

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
            "client_id":FB_APP_ID,
            "redirect_uri":REDIRECT_URI,
            "client_secret":FB_APP_SECRET,
            "code":code,
        },
        timeout=10,
    ).json()
    session["user_token"] = token_resp["access_token"]

    return (
        "✅ Logged in & token stored in session.<br>"
        "Now hit <a href='/debug'>/debug</a> <a href='/pages'>/pages</a> to see granted scopes."
    )

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
    ic(response.status_code,response.json())
    pages = response.json().get("data", [])
    ic(pages[0]['id'])
    session['pages_id'] = pages[0]['id']
    return render_template("pages.html", pages=pages)


@app.route("/post")
def post_to_page():
    user_token = session.get("user_token")
    pages_id = session.get("pages_id")
    page_token = get_page_token(pages_id,session) if pages_id else None

    if not user_token or not pages_id:
        ic("User not logged in or no page selected", user_token, pages_id)
        return redirect("/login")
    

    session['page_token'] = page_token
    response = requests.post(
        f"https://graph.facebook.com/v23.0/{pages_id}/feed",
        params={
            "access_token": page_token,
            "message": "Ferrari"
        }
    )
    ic(response.status_code, response.json())
    return (
        "Post created! Check your Facebook Page.<br>"
        f"Response: {response.json()}"
    )

@app.route('/posts')
def posts():
    user_token = session.get("user_token")
    pages_id = session.get("pages_id")
    posts_niche = session.get("posts_niche")
    if not user_token or not pages_id:
        return redirect("/login")
    page_token = get_page_token(pages_id,session)
    ic(user_token, pages_id, page_token)
    response = requests.get(
        f"https://graph.facebook.com/v23.0/{pages_id}/published_posts",
        params={
            "access_token": page_token,
            "fields": "id,message,created_time"
        }
    )
    ic(response.status_code)
    posts = response.json().get("data", [])
    if not posts_niche:
        posts_niche = query_gemini(
            prompt="Extract the niche of the facebook page that's posting these posts",
            text=posts,
            scheme={'niche': None}
        ).get('niche', None)
        session['posts_niche'] = posts_niche
    else:
        print(f"Using cached niche: {posts_niche}")
    return render_template("posts.html", posts=posts,niche=posts_niche)

if __name__ == "__main__":
    app.run(debug=True, port=5000)  # debug=True for dev convenience