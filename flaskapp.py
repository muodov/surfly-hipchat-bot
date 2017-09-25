import os
import re
import jwt
import requests
from flask import Flask, send_from_directory, json, request, abort, render_template
from raven.contrib.flask import Sentry

from models import Installation
from settings import SENTRY_DSN, SERVER_NAME


app = Flask(__name__)
app.config['ERROR_404_HELP'] = False

sentry = Sentry(dsn=SENTRY_DSN)
if not app.config['DEBUG']:
    sentry.init_app(app)


def validate_auth(token):
    if token:
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
            return installation
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
                "callbackUrl": SERVER_NAME + "install",
                "updateCallbackUrl": SERVER_NAME + "update"
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
                    "pattern": "^/ ",
                    "event": "room_message",
                    "name": "start session"
                }
            ],
            "configurable": {
                "url": SERVER_NAME + "config"
            }
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


@app.route('/update', methods=['POST'])
def update():
    req = request.json
    try:
        installation = Installation.get(
            Installation.oauth_id == req.get('oauthId')
        )
        installation.uninstalled = False
        installation.save()
    except Installation.DoesNotExist:
        pass
    return ''


@app.route('/install/<oauth_id>', methods=['DELETE'])
def uninstall(oauth_id):
    try:
        installation = Installation.get(
            Installation.oauth_id == oauth_id
        )
        installation.uninstalled = True
        installation.save()
    except Installation.DoesNotExist:
        pass
    return ''


@app.route('/start_session', methods=['POST'])
def start_session():
    header = request.headers.get('Authorization')
    if header and header.startswith('JWT '):
        token = header[4:]
        installation = validate_auth(token)
    else:
        abort(401)

    req = request.json

    msg = req['item']['message']['message']
    sender_link = req['item']['message']['from']['links']['self']
    sender_name = req['item']['message']['from']['name']
    room_link = req['item']['room']['links']['self']

    pat_match = re.findall(r'/surfly (.*)', msg)
    start_url = None
    if pat_match:
        start_url = pat_match[0]
    else:
        aliases = []
        try:
            aliases = json.loads(installation.aliases)
        except ValueError:
            pass
        for alias in aliases:
            if alias[0] == msg:
                start_url = alias[1]
                break

    if not start_url:
        return ''

    if not installation.surfly_api_key or not installation.hipchat_user_token:
        return json.jsonify({
            'color': 'yellow',
            'message_format': 'text',
            'notify': True,
            'message': 'Surfly HipChat bot is not configured yet.',
        })

    resp = requests.post(
        'https://api.surfly.com/v2/sessions/',
        params={'api_key': installation.surfly_api_key},
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
            'Authorization': 'Bearer %s' % installation.hipchat_user_token
        }
    )

    resp = requests.post(
        room_link + '/notification',
        json={
            'message_format': 'text',
            'color': 'yellow',
            'notify': True,
            'message': 'Started a Surfly session: {follower_link}. {sender_name} has received the leader link via PM'.format(
                follower_link=follower_link,
                sender_name=sender_name
            ),
        },
        headers={
            'Authorization': 'Bearer %s' % installation.hipchat_user_token
        }
    )

    return ''


@app.route('/config', methods=['GET', 'POST'])
def config():
    jwt_token = request.args.get('signed_request')
    installation = validate_auth(jwt_token)
    aliases = json.loads(installation.aliases)
    for i in range(5):
        if i >= len(aliases):
            aliases.append(['', ''])
    if request.method == 'POST':
        installation.surfly_api_key = request.form.get('surfly_api_key')
        installation.hipchat_user_token = request.form.get('hipchat_api_token')
        installation.aliases = json.dumps([
            (request.form.get('aliaskey0', ''), request.form.get('aliasval0', '')),
            (request.form.get('aliaskey1', ''), request.form.get('aliasval1', '')),
            (request.form.get('aliaskey2', ''), request.form.get('aliasval2', '')),
            (request.form.get('aliaskey3', ''), request.form.get('aliasval3', '')),
            (request.form.get('aliaskey4', ''), request.form.get('aliasval4', '')),
        ])
        installation.save()
        return render_template(
            'config.html',
            installation=installation,
            aliases=aliases,
            notification=True
        )
    else:
        return render_template(
            'config.html',
            installation=installation,
            aliases=aliases,
        )


@app.route('/<path:path>')
def static_file(path):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'root'),
        path
    )
