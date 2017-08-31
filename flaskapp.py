import os
from flask import Flask, send_from_directory, json, request
from raven.contrib.flask import Sentry

from settings import SENTRY_DSN, SURFLY_API_KEY


app = Flask(__name__)
app.config['ERROR_404_HELP'] = False
app.config.update(
    SURFLY_API_KEY=SURFLY_API_KEY,
)

sentry = Sentry(dsn=SENTRY_DSN)
if not app.config['DEBUG']:
    sentry.init_app(app)


@app.route('/capabilities')
def capabilities_descriptor():
    return json.jsonify({
        "name": "Surfly Hipchat Integration",
        "description": "A bot that can start cobrowsing sessions from Hipchat",
        "key": "com.muodov.surfly",
        "links": {
            "homepage": "https://surfly-hipchat.herokuapp.com/",
            "self": "https://surfly-hipchat.herokuapp.com/capabilities"
        },
        "capabilities": {
            "hipchatApiConsumer": {
                "fromName": "Surfly Bot",
                "avatar": "https://surfly-hipchat.herokuapp.com/avatar.png",
                "scopes": [
                    "send_notification",
                    "send_message"
                ]
            },
            "webhook": [
                {
                    "url": "https://surfly-hipchat.herokuapp.com/start_session",
                    "authentication": "jwt",
                    "pattern": "^/surfly ",
                    "event": "room_message",
                    "name": "start session"
                }
            ]
        }
    })


@app.route('/start_session', methods=['POST'])
def start_session():
    if request.method == 'POST':
        req = request.json
        print(req)

        follower_link = 'https://surfly.com/123-123-123'
        return json.jsonify({
            'message_format': 'text',
            'notify': True,
            'message': 'Started a Surfly session at %s' % follower_link,
        })


@app.route('/<path:path>')
def static_file(path):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'root'),
        path
    )
