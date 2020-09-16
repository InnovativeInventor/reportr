from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from fastapi import FastAPI, Depends, HTTPException, status
from typing import List
from fastapi.staticfiles import StaticFiles
import secrets
import json
import mongoset

## Credit: some auth code is from the authlib docs

config = Config('.env')  # read config from .env file
oauth = OAuth(config)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

## API creation
app = FastAPI()
backend = FastAPI()

## Adding middleware and database
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(16))
db = mongoset.connect(db_name="reportr")

@backend.route('/login')
async def login(request: Request):
    # absolute url for callback
    # we will define it below
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@backend.route('/auth')
async def auth(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    if user.get("hd") == "choate.edu" and user.get("email").endswith("@choate.edu"):
        request.session['user'] = dict(user)
        print(user)
        return RedirectResponse(url="/report.html")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized email account/address. Are you authenticated?",
        )

@backend.route('/report')
async def report(request: Request, instigators: List[str], witnesses: List[str], priority: int, description: str):
    user = request.session.get('user')
    if user:
        reporter = json.dumps(user)
        success = db.insert({"reporter": reporter, "instigators": instigators, "witnesses": witnesses, "priority": priority, "description": description})

        return {"Success": success}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized call. Are you authenticated?",
    )

## API mounting
app.mount("/backend", backend)
app.mount("/", StaticFiles(directory="static"), name="static")
