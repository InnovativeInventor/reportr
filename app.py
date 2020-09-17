from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from fastapi import FastAPI, Depends, HTTPException, status, Response
from typing import List
from fastapi.staticfiles import StaticFiles
import secrets
import csv
import json
import time
import yaml
import io
import mongoset
from fastapi.responses import JSONResponse, StreamingResponse

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
db = mongoset.connect(db_name="reportr")["reportr"]
with open("admin.yaml") as f:
    admins = yaml.load(f).get("admins")

@app.route("/")
async def index(request: Request):
    user = request.session.get('user')
    if email := await authenticate_user(user):
        return RedirectResponse(url="/report.html")
    return RedirectResponse(url="/index.html")

@backend.route('/login')
async def login(request: Request):
    # absolute url for callback
    # we will define it below
    user = request.session.get('user')
    if email := await authenticate_user(user):
        print(email)
        return RedirectResponse(url="/report.html")
    else:
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
    if email := await authenticate_user(user):
        success = db.insert({"reporter": email, "instigators": instigators, "witnesses": witnesses, "priority": priority, "description": description, "time": int(time.time())})
        return {"Success": success}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized call. Are you authenticated?",
    )


@backend.get("/json")
async def export_json(request: Request):
    user = request.session.get('user')
    if email := await authenticate_user(user):
        if email in admins:
            return JSONResponse(db.all())

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized call. Are you authenticated?",
    )

@backend.get("/csv")
async def export_csv(request: Request, response: Response):
    user = request.session.get('user')
    if email := await authenticate_user(user):
        if email in admins:
            reports = db.all()

            ## Generate CSV
            string = io.StringIO()
            fieldnames = reports[0].keys()
            writer = csv.DictWriter(string, fieldnames=fieldnames)

            writer.writeheader()
            for each_response in reports:
                for field in each_response: # flatten
                    if isinstance(field, int):
                        each_response[field] = " ".join(each_response[field])

                writer.writerow(each_response)
            
            ## Generate and return response
            return StreamingResponse(content=iter([string.getvalue()]), media_type="text/csv")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized call. Are you authenticated?",
    )

async def authenticate_user(user):
    if user and user.get("hd") == "choate.edu" and user.get("email").endswith("@choate.edu"):
            return user.get("email")
    return False


## API mounting
app.mount("/backend", backend)
app.mount("/", StaticFiles(directory="static"), name="static")
