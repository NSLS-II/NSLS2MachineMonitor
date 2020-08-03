import time
from datetime import datetime
import yaml
import logging

from slack import WebClient
from slack.errors import SlackApiError
from caproto.threading.client import Context

import logging
logging.basicConfig(filename='example.log',level=logging.DEBUG)

pv_data = dict()
pv_data['_updated'] = False
pv_data['_update'] = 0


def read_config(filename='secrets.yml'):
    logging.debug("Reading config file %s", filename)
    with open(filename) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    return config


def post_message(message, config):
    client = WebClient(token=config['token'])
    channel = config['channel']
    try:
        response = client.chat_postMessage(
            channel=channel, text=message)
        assert response["message"]["text"] == message
        logging.debug("Send message \"%s\" to channel %s", message, channel)
    except SlackApiError as e:
        assert e.response["ok"] is False
        assert e.response["error"]
        logging.error("SLACK Client reported error %s", e.response['error'])


def term_string(array):
    for a in array:
        if a == 0:
            break
        else:
            yield a


def pv_callback(sub, response):
    msg = ""

    msg = "".join(map(chr, 
        [c for c in term_string(response.data)]))
    
    pv_data[sub.pv.name] = msg
    pv_data['_update'] = time.time()
    pv_data['_updated'] = False

    timestamp = response.metadata.timestamp
    if timestamp > pv_data["timestamp"]:
        pv_data['timestamp'] = timestamp

    logging.debug('Received response \"%s\" from %s', response, sub.pv.name)


def setup_pvs(pv_names):
    ctx = Context()
    pvs = ctx.get_pvs(*pv_names)
    for pv in pvs:
        sub = pv.subscribe(data_type='time')
        sub.add_callback(pv_callback)
        pv_data[pv.name] = ""
        logging.debug("Subscribed to PV : %s", pv.name)

    pv_data['timestamp'] = 0
    return sub


if __name__ == "__main__":
    config = read_config()
    sub = setup_pvs(config['pvs']['msg'])

    time.sleep(config['main']['startup_delay'])

    while(True):
        delta = time.time() - pv_data['_update']
        if (delta > 30) and (pv_data['_updated']) is False:
            msg = str(datetime.fromtimestamp(pv_data['timestamp']))
            msg += " : "
            msg += ", ".join([pv_data[m] for m in config['pvs']['msg']])
            post_message(msg, config['slack'])
            pv_data['_updated'] = True
        time.sleep(config['main']['poll_time'])
