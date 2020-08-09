import os
import sys
import time
from datetime import datetime
import argparse
import yaml
import logging

from slack import WebClient
from slack.errors import SlackApiError
import caproto
from caproto.threading.client import Context
# from caproto.asyncio.client import Context

logger = logging.getLogger(__name__)

global_data = dict()
global_pv_data = dict()

captoto_logger = logging.getLogger(caproto.__name__)
captoto_logger.setLevel(logging.WARNING)


def read_config(filename):
    logger.debug("Reading config file %s", filename)
    with open(filename) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    return config


def post_message(text, blocks, config):
    client = WebClient(token=os.environ["SLACK_API_TOKEN"])
    channel = config['channel']
    logger.debug(
        "Sending message to channel %s = %s : %s",
        channel, str(text).replace('\n', '\\n'),
        str(blocks).replace('\n', '\\n'))

    try:
        response = client.chat_postMessage(
            channel=channel, text=text, blocks=blocks)
        logger.debug(
            "Slack message response %s",
            str(response["message"]).replace('\n', '\\n'))
        return True
    except SlackApiError as e:
        assert e.response["ok"] is False
        assert e.response["error"]
        logger.error("SLACK Client reported error %s", e.response['error'])
        return False


def term_string(array):
    for a in array:
        if a == 0:
            break
        else:
            yield a


def data_callback(sub, response):
    logger.debug("Entered data callback for %s", sub.pv.name)
    logger.debug('Received response \"%s\" from %s', response, sub.pv.name)

    global_pv_data[sub.pv.name]['value'] = response.data
    global_pv_data[sub.pv.name]['timestamp'] = response.metadata.timestamp


def trigger_callback(sub, response):
    logger.debug("Entered trigger callback for %s", sub.pv.name)
    logger.debug('Received response \"%s\" from %s', response, sub.pv.name)

    global_data['last_trigger'] = time.time()
    global_data['trigger_timestamp'] = response.metadata.timestamp
    global_data['triggered'] = True
    logger.debug('Trigger time = %d', global_data['last_trigger'])


def subscribe_pvs(ctx, pv_names, callback):
    pvs = ctx.get_pvs(*pv_names)
    for pv in pvs:
        logger.debug('Setting up PV %s', pv)
        sub = pv.subscribe(data_type='time')
        sub.add_callback(callback)
        global_pv_data[pv.name] = dict(value=None, timestamp=None)


def setup_pvs(pv_config):
    logger.debug("pv_config = %s", pv_config)

    ctx = Context()

    pv_names = [cfg['pv'] for cfg in pv_config['message']]
    subscribe_pvs(ctx, pv_names, data_callback)

    pv_names = [cfg['pv'] for cfg in pv_config['trigger']]
    subscribe_pvs(ctx, pv_names, trigger_callback)

    global_data['timestamp'] = 0


def format_message_blocks(config):
    blocks = list()

    logger.debug("global_pv_data = %s", global_pv_data)

    head_text = config['message']['head']
    head_text += " on "
    head_text += datetime.fromtimestamp(
        global_data["trigger_timestamp"]).strftime(
        config['message']['time_format'])

    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": head_text
        }
    })

    text = ""
    for pv in config['pvs']['message']:
        logger.debug("Formatting PV %s", pv['pv'])

        # Format
        val = None
        if "enum" in pv:
            val = pv['enum'][global_pv_data[pv['pv']]['value'][0]]
        elif "numerical" in pv:
            val = global_pv_data[pv['pv']]['value'][0]
        else:
            val = "".join(map(chr,
                          [c for c in term_string(
                              global_pv_data[pv['pv']]['value'])]))

        msg = pv['format'].format(val)
        logger.debug("msg = %s", msg)
        text += msg
        text += "\n"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text
        }
    })

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": config['message']['tail']
        }
    })

    if config['message']['divider']:
        blocks.append({
            "type": "divider"
        })

    return head_text, blocks


def main_loop(config):
    last_update = time.time()
    while(True):
        if global_data['triggered']:
            delta = time.time() - global_data['last_trigger']
            if delta > config['main']['update_delay']:
                logger.debug("Trigger message send ....")
                text, msg_blocks = format_message_blocks(config)

                if post_message(text, msg_blocks, config['slack']):
                    global_data['triggered'] = False
                    last_update = time.time()
        if config['main']['beacon']:
            delta = time.time() - last_update
            if delta > config['main']['beacon_delay']:
                if post_message(config['main']['beacon_message'],
                                None, config['slack']):
                    last_update = time.time()
        else:
            last_update = time.time()

        time.sleep(config['main']['poll_time'])


def main():
    # Read command line arguments
    parser = argparse.ArgumentParser(
        description='NSLS2 Machine Monitor Slack Server')
    parser.add_argument('--loglevel', dest='loglevel', default='error')
    parser.add_argument('--log', dest='logfile', default=None)
    parser.add_argument('--config', dest='configfile', default='nsls2mm.yml')

    args = parser.parse_args()

    # Check for token
    if not "SLACK_API_TOKEN" in os.environ:
        raise ValueError("No SLACK_API_TOKEN in environmental variables.")

    # Setup logger

    loglevel = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(loglevel, int):
        raise ValueError('Invalid log level: %s' % args.loglevel.upper())

    _log = dict()
    if args.logfile is None:
        _log['stream'] = sys.stderr
    else:
        _log['filename'] = args.logfile

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(threadName)s - %(levelname)s"
        " - %(message)s",
        datefmt='%m/%d/%Y %I:%M:%S %p', level=loglevel, **_log)

    # Set defaults
    global_data['triggered'] = False
    global_data['last_trigger'] = time.time()

    # Read Yaml Config File
    config = read_config(args.configfile)

    # Setup PV Monitoring
    setup_pvs(config['pvs'])

    # Wait for connections etc.....
    time.sleep(config['main']['startup_delay'])

    # Engage .....
    main_loop(config)
