import time
from datetime import datetime
import argparse
import yaml
import logging

from slack import WebClient
from slack.errors import SlackApiError
import caproto
from caproto.threading.client import Context

logger = logging.getLogger(__name__)

pv_data = dict()
pv_data['_updated'] = False
pv_data['_update'] = 0

captoto_logger = logging.getLogger(caproto.__name__)
captoto_logger.setLevel(logging.WARNING)


def read_config(filename):
    logger.debug("Reading config file %s", filename)
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
        logger.debug("Send message \"%s\" to channel %s", message, channel)
    except SlackApiError as e:
        assert e.response["ok"] is False
        assert e.response["error"]
        logger.error("SLACK Client reported error %s", e.response['error'])


def term_string(array):
    for a in array:
        if a == 0:
            break
        else:
            yield a


def pv_callback(sub, response):
    msg = ""

    msg = "".join(map(chr, [c for c in term_string(response.data)]))

    pv_data[sub.pv.name] = msg
    pv_data['_update'] = time.time()
    pv_data['_updated'] = False

    timestamp = response.metadata.timestamp
    if timestamp > pv_data["timestamp"]:
        pv_data['timestamp'] = timestamp

    logger.debug('Received response \"%s\" from %s', response, sub.pv.name)


def setup_pvs(pv_names):
    ctx = Context()
    pvs = ctx.get_pvs(*pv_names)
    for pv in pvs:
        sub = pv.subscribe(data_type='time')
        sub.add_callback(pv_callback)
        pv_data[pv.name] = ""
        logger.debug("Subscribed to PV : %s", pv.name)

    pv_data['timestamp'] = 0
    return sub


def main_loop(config):
    while(True):
        delta = time.time() - pv_data['_update']
        if (delta > 30) and (pv_data['_updated']) is False:
            msg = str(datetime.fromtimestamp(pv_data['timestamp']))
            msg += " : "
            msg += ", ".join([pv_data[m] for m in config['pvs']['msg']])
            post_message(msg, config['slack'])
            pv_data['_updated'] = True
        time.sleep(config['main']['poll_time'])


def main():
    # Read command line arguments
    parser = argparse.ArgumentParser(
        description='NSLS2 Machine Monitor Slack Server')
    parser.add_argument('--loglevel', dest='loglevel', default='error')
    parser.add_argument('--log', dest='logfile', default='nsls2mm.log')
    parser.add_argument('--config', dest='configfile', default='nsls2mm.yml')

    args = parser.parse_args()

    # Setup logger

    loglevel = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(loglevel, int):
        raise ValueError('Invalid log level: %s' % args.loglevel.upper())

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(threadName)s - %(levelname)s"
        " - %(message)s",
        datefmt='%m/%d/%Y %I:%M:%S %p', level=loglevel, filename=args.logfile)

    # Read Yaml Config File

    config = read_config(args.configfile)

    # Setup PV Monitoring
    setup_pvs(config['pvs']['msg'])

    # Wait for connections etc.....
    time.sleep(config['main']['startup_delay'])

    # Engage .....
    main_loop(config)
