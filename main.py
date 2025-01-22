from flask import Flask, request, render_template, session, redirect, flash
from flask_session import Session
from pymongo import MongoClient
from dotenv import load_dotenv
import os, requests
from bson.objectid import ObjectId

load_dotenv()

client = MongoClient(os.getenv('MONGO_URI'))
db = client['org_inviter']
app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = os.getenv('SECRET_KEY')
Session(app)

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = " ".join(["admin:org"])
API_BASE = "https://api.github.com"

@app.route('/')
def index():
    return render_template('landing.html')

@app.route("/home")
def home():
    user = session.get('user')
    if user is None:
        return redirect('/login')
    user = int(user)
    
    links = db.links.find({"creator": user})
    links = list(links)

    for l in range(len(links)):
        link = links[l]
        r = requests.get(f"{API_BASE}/orgs/{link['org']}", headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + db.tokens.find_one({"user": link['creator']})['token']
        })
        org = r.json()
        links[l]['org'] = org

        r = requests.get(f"{API_BASE}/orgs/{link['org']['login']}/teams", headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + db.tokens.find_one({"user": link['creator']})['token']
        })
        teams = r.json()
        t = []
        for team in teams:
            if str(team['id']) in link['teams']:
                t.append(team)
            
        links[l]['teams'] = t
        links[l]['teamStr'] = ", ".join([team['name'] for team in link['teams']])

    token = db.tokens.find_one({"user": user})
    allowedOrgs = []

    r = requests.get(f"{API_BASE}/user/memberships/orgs?per_page=100&page=1", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token['token']
    })
    for org in r.json():
        if org['role'] == 'admin':
            org = org['organization']
            teams = requests.get(f"{API_BASE}/orgs/{org['login']}/teams", headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token['token']
            })
            teams = teams.json()
            org['teams'] = teams
            allowedOrgs.append(org)

    return render_template('home.html', links=links, orgs=allowedOrgs)

@app.route("/login")
def login():
    if request.args.get('invite') is not None:
        session['invite'] = request.args.get('invite')
    SCOPE_L = SCOPE
    if request.args.get('no_scope') is not None:
        SCOPE_L = ""
    return redirect(f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPE_L}&prompt=true")

@app.route("/callback")
def callback():
    code = request.args.get('code')
    if code is None:
        return redirect('/login')
    
    r = requests.post("https://github.com/login/oauth/access_token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }, headers={
        "Accept": "application/json"
    })

    if r.status_code != 200:
        return redirect('/login')

    data = r.json()
    token = data['access_token']

    r = requests.get(f"{API_BASE}/user", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token
    })

    if r.status_code != 200: return redirect('/login')

    userId = r.json()['id']
    session['user'] = userId
    db.tokens.update_one({
        "user": userId,
    }, {
        "$set": {
            "token": token
        }
    }, upsert=True)

    if session.get('invite') is not None:
        return redirect('/invite/' + session.get('invite'))
    return redirect('/home')

@app.post("/link/create")
def createLink():
    user = session.get('user')
    if user is None:
        return redirect('/login')
    
    org = request.form.get('org')
    teams = request.form.getlist('teams')

    link = db.links.insert_one({
        "creator": user,
        "org": org,
        "teams": teams
    })

    flash("Link created successfully! Your invite link is: https://inviter.shuchir.dev/invite/" + str(link.inserted_id))
    return redirect('/home')

@app.post("/link/delete")
def deleteLink():
    user = session.get('user')
    if user is None:
        return redirect('/login')
    
    linkId = request.form.get('id')
    db.links.delete_one({
        "_id": ObjectId(linkId)
    })

    return redirect('/home')

@app.get("/invite/<linkId>")
def invite(linkId):
    link = db.links.find_one({
        "_id": ObjectId(linkId)
    })

    user = session.get('user')
    if user is None:
        return redirect('/login?invite=' + linkId + "&no_scope=true")

    userToken = db.tokens.find_one({"user": user})['token']
    creatorToken = db.tokens.find_one({"user": link['creator']})['token']

    r = requests.get(f"{API_BASE}/user", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + userToken
    })
    user = r.json()

    r = requests.get(f"{API_BASE}/orgs/{link['org']}", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + creatorToken
    })
    org = r.json()

    r = requests.get(f"{API_BASE}/orgs/{link['org']}/teams", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + creatorToken
    })
    teams = r.json()
    for team in teams:
        if str(team['id']) not in link['teams']:
            teams.remove(team)
        
    return render_template('confirm.html', org=org, teams=teams, linkId=linkId, user=user)

@app.post("/invite/<inviteId>")
def send(inviteId):
    link = db.links.find_one({
        "_id": ObjectId(inviteId)
    })

    user = session.get("user")
    userToken = db.tokens.find_one({"user": user})['token']
    creatorToken = db.tokens.find_one({"user": link['creator']})['token']

    username = requests.get(f"{API_BASE}/user", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + userToken
    }).json()['login']
    
    membershipCheck = requests.get(f"{API_BASE}/orgs/{link['org']}/members/{username}", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + creatorToken
    })
    if membershipCheck.status_code == 204:
        flash("You are already a member of this organization!")
        return render_template("result.html")

    r = requests.post(f"{API_BASE}/orgs/{link['org']}/invitations", json={
        "invitee_id": user,
        "team_ids": [int(team) for team in link['teams']],        
    }, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + creatorToken
    })

    org = requests.get(f"{API_BASE}/orgs/{link['org']}", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + creatorToken
    }).json()

    if r.status_code == 201:
        return redirect(f"https://github.com/orgs/{org['login']}/invitation")
    else:
        print(r.json())
        flash("Failed to send invite! Please contact the organization admin.")
    
    return render_template("result.html")

app.run(host='0.0.0.0', debug=True)