import os
import re
import jwt
import requests
from flask import Flask, send_from_directory, json, request, abort
from raven.contrib.flask import Sentry

from models import Installation
from settings import SENTRY_DSN, SURFLY_API_KEY, HIPCHAT_AUTH_TOKEN, SERVER_NAME


app = Flask(__name__)
app.config['ERROR_404_HELP'] = False
app.config.update(
    SURFLY_API_KEY=SURFLY_API_KEY,
    HIPCHAT_AUTH_TOKEN=HIPCHAT_AUTH_TOKEN
)

sentry = Sentry(dsn=SENTRY_DSN)
if not app.config['DEBUG']:
    sentry.init_app(app)


def validate_auth(request):
    header = request.headers.get('Authorization')
    if header and header.startswith('JWT '):
        token = header[4:]
        try:
            payload = jwt.decode(token, verify=False)
            installation = Installation.get(
                Installation.oauth_id == payload['iss']
            )
            jwt.decode(token, key=installation.oauth_secret)
        except Exception as e:
            print(e, token)
            abort(401)
    else:
        abort(401)


@app.route('/capabilities')
def capabilities_descriptor():
    return json.jsonify({
        "name": "Surfly Hipchat Integration",
        "description": "A bot that can start cobrowsing sessions from Hipchat",
        "key": "com.muodov.surfly",
        "links": {
            "homepage": SERVER_NAME,
            "self": SERVER_NAME + "capabilities"
        },
        "capabilities": {
            "installable": {
                "callbackUrl": SERVER_NAME + "install"
            },
            "hipchatApiConsumer": {
                "fromName": "Surfly Bot",
                "avatar": SERVER_NAME + "avatar.png",
                "scopes": [
                    "send_notification",
                    "send_message"
                ]
            },
            "webhook": [
                {
                    "url": SERVER_NAME + "start_session",
                    "authentication": "jwt",
                    "pattern": "^/surfly ",
                    "event": "room_message",
                    "name": "start session"
                }
            ]
        }
    })


@app.route('/install', methods=['POST'])
def install():
    req = request.json
    installation = Installation(
        oauth_id=req.get('oauthId'),
        oauth_secret=req.get('oauthSecret'),
        capabilities_url=req.get('capabilitiesUrl'),
        room_id=req.get('roomId'),
        group_id=req.get('groupId'),
    )
    installation.save()
    return ''


@app.route('/start_session', methods=['POST'])
def start_session():
    if request.method == 'POST':
        validate_auth(request)

        req = request.json

        msg = req['item']['message']['message']
        sender_link = req['item']['message']['from']['links']['self']
        sender_name = req['item']['message']['from']['name']

        pat_match = re.findall(r'/surfly (.*)', msg)
        if not pat_match:
            return ''

        start_url = pat_match[0]

        resp = requests.post(
            'https://api.surfly.com/v2/sessions/',
            params={'api_key': app.config['SURFLY_API_KEY']},
            json={
                'url': start_url,

            },
            timeout=5
        )

        if resp.status_code != 200:
            err_msg = str(resp.status_code)
            try:
                err_msg += str(resp.json())
            except:
                pass
            return json.jsonify({
                'color': 'red',
                'message_format': 'text',
                'notify': True,
                'message': 'Error while creating a session: %s' % err_msg,
            })

        resp_data = resp.json()
        follower_link = resp_data['viewer_link']
        leader_link = resp_data['leader_link']

        requests.post(
            sender_link + '/message',
            json={
                'message': 'Open this link to start the session: <a href="{link}">{link}</a>'.format(
                    link=leader_link
                ),
                'notify': True,
                'message_format': 'html',
            },
            headers={
                'Authorization': 'Bearer %s' % app.config['HIPCHAT_AUTH_TOKEN']
            }
        )

        return json.jsonify({
            'message_format': 'text',
            'notify': True,
            'message': 'Started a Surfly session: {follower_link}. {sender_name} has received the leader link via PM'.format(
                follower_link=follower_link,
                sender_name=sender_name
            ),
        })


@app.route('/<path:path>')
def static_file(path):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'root'),
        path
    )
