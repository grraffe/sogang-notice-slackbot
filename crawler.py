import os
from bson.json_util import dumps

import slack
import requests

from flask import Flask
from flask import request
from flask import make_response

from pymongo import MongoClient
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_notices_from_mongo(notice_type):
    client = MongoClient(os.environ['srv'])
    notices = []
    cursor = client.slackbot.notices.find({'type': notice_type})
    for notice in cursor:
        notices.append(notice)
    return notices

def get_board_info(notice_type):
    client = MongoClient(os.environ['srv'])
    cursor = None
    if notice_type:
        cursor = client.slackbot.notice_url.find({'type': notice_type})
    else:
        cursor = client.slackbot.notice_url.find()
    board_infos = []
    for board_info in cursor:
        board_infos.append(board_info)
    return board_infos

def update_notices_to_mongo(notice_type, notices):
    try:
        client = MongoClient(os.environ['srv'])
        client.slackbot.notices.delete_many({'type': notice_type})
        client.slackbot.notices.insert_many(notices)
    except Exception as e:
        raise e

def get_notice_block(notice):
    emoji = {
        'haksa': ':books:',
        'janghak': ':money_with_wings:',
        'corona': ':mask:',
        'ilban': ':mega:'
    }
    return [
        {
            'type': 'section',
            'text': {
                'type': "mrkdwn",
                'text': "*<{}|{}>*".format(notice['url'], notice['title'])
            }
        },
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': '*{}* | {}*{}*{}'.format(notice['date'], emoji[notice['type']], notice['board_name'], emoji[notice['type']])
                }
            ]
        }
    ]

def get_divider():
    return [
        {
            'type': 'divider'
        }
    ]

def get_notices(board_info):
    BASE_URL = 'https://sogang.ac.kr'
    past_notices = get_notices_from_mongo(board_info['type'])
    r = requests.get(board_info['url'])
    soup = BeautifulSoup(r.text, 'html.parser')
    notices = soup.find_all('tr', class_='notice')
    notices = [notice.find_all('td') for notice in notices]
    notices = [(x[1].find('span').text.strip(), x[1].find('a')['href'].strip(), x[4].text.strip()) for x in notices]
    notices = [(x[0], x[1].encode('utf-8').replace(b'\xc2\xa4', b'&').decode('utf-8'), x[2]) for x in notices]
    notices = [{'title': x[0], 'url': BASE_URL + x[1], 'date': x[2], 'board_name': board_info['name'], 'type': board_info['type']} for x in notices]
    new_notices = list(filter(lambda x: x['url'] not in [y['url'] for y in past_notices], notices))
    return (notices, new_notices)

@app.route('/')
def main():
    all_new_notices = []
    notice_type = request.args.get('type', None)
    board_infos = get_board_info(notice_type)
    blocks = []
    for board_info in board_infos:
        notices, new_notices = get_notices(board_info)
        update_notices_to_mongo(board_info['type'], notices)
        slack_client = slack.WebClient(token=os.environ['SLACK_API_TOKEN'])
        for notice in new_notices:
            if len(blocks) > 0:
                blocks.extend(get_divider())
            blocks.extend(get_notice_block(notice))
            all_new_notices.append(notice)
    if len(blocks) > 0:
        slack_client.chat_postMessage(
            channel='CV6MFML9G',
            text='업데이트에 실패했습니다',
            blocks=blocks
        )

    return make_response({'notices': dumps(all_new_notices)}, 200)


if __name__ == "__main__":
    app.run()
