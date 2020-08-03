import time
from datetime import datetime
import yaml
from slack import WebClient
from slack.errors import SlackApiError
from caproto.threading.client import Context


pv_data = dict()
pv_data['_updated'] = False
pv_data['_update'] = 0


def read_config(filename='secrets.yml'):
    with open(filename) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    return config


def post_message(message, config):
    client = WebClient(token=config['token'])

    try:
        response = client.chat_postMessage(
            channel=config['channel'],
            text=message)
        assert response["message"]["text"] == message
    except SlackApiError as e:
        assert e.response["ok"] is False
        assert e.response["error"]
        print(f"Got an error: {e.response['error']}")


def pv_callback(sub, response):
    msg = "".join(map(chr, [c for c in response.data if c != 0]))
    
    pv_data[sub.pv.name] = msg
    pv_data['_update'] = time.time()
    pv_data['_updated'] = False

    timestamp = response.metadata.timestamp
    if timestamp > pv_data["timestamp"]:
        pv_data['timestamp'] = timestamp

    print('Received response from', sub.pv.name, response)
    print(pv_data)


def setup_pvs(pv_names):
    ctx = Context()
    pvs = ctx.get_pvs(*pv_names)
    for pv in pvs:
        sub = pv.subscribe(data_type='time')
        sub.add_callback(pv_callback)
        pv_data[pv.name] = ""

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
        print(delta, pv_data)
        time.sleep(config['main']['poll_time'])
