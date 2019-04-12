#!/usr/bin/env python3
import contextlib
import logging
import time

__author__ = 'jota'

import ctypes
import gzip
import json
import os
import smtplib
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from io import BytesIO

#gmail api code
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
from email.mime.text import MIMEText
from apiclient import errors, discovery

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CREDENTIALS_FILE_NAME = '.gmail_credentials.json'


def init_gmail(config):
    """Gets a gmail service object.
    """
    TOKENPICKLE_FILE_NAME = '.gmail_token.pickle'
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKENPICKLE_FILE_NAME):
        with open(TOKENPICKLE_FILE_NAME, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE_NAME, SCOPES)
            set_windows_hidden_file(CREDENTIALS_FILE_NAME)
            if config['email']['gmail']['console_oauth']:
                creds = flow.run_console()
            else:
                creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(TOKENPICKLE_FILE_NAME, 'wb') as token:
            pickle.dump(creds, token)
            set_windows_hidden_file(TOKENPICKLE_FILE_NAME)

    service = build('gmail', 'v1', credentials=creds)
    return service


def create_message(sender, to, subject, message_text):
    """Create a message for an email.

    Args:
      sender: Email address of the sender.
      to: Email address of the receiver.
      subject: The subject of the email message.
      message_text: The text of the email message.

    Returns:
      An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw.decode()}


def send_message(service, user_id, message):
    """Send an email message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      message: Message to be sent.

    Returns:
      Sent Message.
    """
    try:
        message = (service.users().messages().send(userId=user_id, body=message).execute())
        logging.info('Message Id: ' + message['id'])
        return message
    except errors.HttpError as error:
        logging.warning('An error occurred: ' + error)
#end of gmail api code


def set_windows_hidden_file(filename, hidden = True):
    # https://stackoverflow.com/questions/25432139/python-cross-platform-hidden-file
    # Just Windows things
    if os.name != 'nt': return
    if not os.path.isfile(filename): return
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    INVALID_FILE_ATTRIBUTES = -1
    FILE_ATTRIBUTE_HIDDEN = 2
    FILE_ATTRIBUTE_UNHIDE = ~FILE_ATTRIBUTE_HIDDEN
    attrs = kernel32.GetFileAttributesW(filename)
    try:
        if attrs == INVALID_FILE_ATTRIBUTES:
            raise ctypes.WinError(ctypes.get_last_error())
        if hidden:
            attrs |= FILE_ATTRIBUTE_HIDDEN
        else:
            attrs &= FILE_ATTRIBUTE_UNHIDE
        if not kernel32.SetFileAttributesW(filename, attrs): 
            raise ctypes.WinError(ctypes.get_last_error())
    except OSError as e:
        logging.warning(f'Could not set file attributes for "{filename}". Error returned: ' + str(e))
        

MAIN_URL = 'https://chrono.gg'
POST_URL = 'https://api.chrono.gg/quest/spin'
ALREADY_CLICKED_CODE = 420
UNAUTHORIZED = 401
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
GLOBAL_HEADERS = {'User-Agent': USER_AGENT, 'Pragma': 'no-cache', 'Origin': MAIN_URL,
                  'Accept-Encoding': 'gzip, deflate, br', 'Accept': 'application/json', 'Cache-Control': 'no-cache',
                  'Connection': 'keep-alive', 'Referer': MAIN_URL}
COOKIE_FILE_NAME = ".chronogg"
CONFIG_FILE_NAME = ".config"


@contextlib.contextmanager
def setup_logging():
    logger = logging.getLogger()
    try:
        if os.environ["DEBUG"]:
            logger.setLevel(logging.DEBUG)
    except KeyError:
        logger.setLevel(logging.INFO)
    try:
        # __enter__

        # Generic file logging
        # log_filename = 'AutoChronoGG_{}.log'.format(time.strftime("%Y%m%d-%H%M%S"))
        # f_handler = logging.FileHandler(filename=log_filename, encoding='utf-8', mode='w')

        s_handler = logging.StreamHandler(stream=sys.stdout)
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter(
            '%(asctime)s %(levelname)-5.5s [%(name)s] [%(funcName)s()] %(message)s <line %(lineno)d>',
            dt_fmt,
            style='%')
        # add f_handler in list to add file logging
        for handler in [s_handler]:
            handler.setFormatter(fmt)
            logger.addHandler(handler)

        yield
    finally:
        # __exit__
        handlers = logger.handlers[:]
        for hdlr in handlers:
            hdlr.close()
            logger.removeHandler(hdlr)


def get_web_page(url, headers, cookies):
    try:
        logging.info(f'Fetching {url}')
        request = urllib.request.Request(url, None, headers)
        request.add_header('Authorization', cookies)
        response = urllib.request.urlopen(request)
        if response.info().get('Content-Encoding') == 'gzip':
            buf = BytesIO(response.read())
            f = gzip.GzipFile(fileobj=buf)
            r = f.read()
        else:
            r = response.read()
        return r
    except urllib.error.HTTPError as e:
        logging.warning(f"Error processing webpage: {e}")
        if e.code == ALREADY_CLICKED_CODE:
            return ALREADY_CLICKED_CODE
        if e.code == UNAUTHORIZED:
            return UNAUTHORIZED
        return None


def save_cookie(cookie):
    set_windows_hidden_file(COOKIE_FILE_NAME, hidden=False)
    with open(COOKIE_FILE_NAME, 'w') as f:
        f.write(cookie)
    set_windows_hidden_file(COOKIE_FILE_NAME)


def get_cookie_from_file():
    try:
        with open(COOKIE_FILE_NAME, 'r') as f:
            return f.read()
    except:
        return ''


def get_config_from_file():
    try:
        with open(CONFIG_FILE_NAME, 'r') as f:
            return json.load(f)
    except:
        return False


def config_exists():
    return os.path.exists(CONFIG_FILE_NAME)


def send_mail(config, subject, body):
    if config and config['email']['enabled']:
        recipients = []
        for email in config['email']['to']:
            recipients.append(email['name'] + ' <' + email['address'] + '>')
        frm = {
            'name': config['email']['from']['name'],
            'address': config['email']['from']['address']
        }
        frm = frm['name'] + ' <' + frm['address'] + '>'
        to = ', '.join(recipients)
        try:
            if config['email']['gmail']['enabled']:
                msg = create_message(frm, to, subject, body)
                send_message(init_gmail(config), 'me', msg)
            else:
                msg = EmailMessage()
                msg['Subject'] = subject
                msg['From'] = frm
                msg['To'] = to
                msg.set_content(body)
                server = smtplib.SMTP(config['email']['server'])
                server.send_message(msg)
                server.quit()
        except FileNotFoundError as e:
            if (e.filename == CREDENTIALS_FILE_NAME):
                logging.warning('An error occurred while sending an e-mail alert. '
                             'Please go to: "https://developers.google.com/gmail/api/quickstart/python", '
                             f'complete step 1 and save "{CREDENTIALS_FILE_NAME}" to the same directory '
                             'as this script.')
        except:
            logging.warning('An error occurred while sending an e-mail alert.'
                         ' Please check your configuration file or your mail server.')
            raise


def main():
    try:
        config = get_config_from_file()
        if config_exists():
            if not config:
                CONFIG_ERR_STR = (f'An error occurred while trying to load the config from file.'
                                  f' Check the JSON syntax in {CONFIG_FILE_NAME}.')
                logging.error(CONFIG_ERR_STR)
                send_mail(config=config, subject='AutoChronoGG: Config error', body=CONFIG_ERR_STR)
                return
        if len(sys.argv) < 2:
            gg_cookie = get_cookie_from_file()
            if not gg_cookie or len(gg_cookie) < 1:
                MISSING_TOKEN_ERR_STR = ('<<<AutoChronoGG>>>\n'
                                         'Usage: ./chronogg.py <Authorization Token>\n'
                                         'Please read the README.md and follow the instructions on '
                                         'how to extract your authorization token.')
                logging.warning(MISSING_TOKEN_ERR_STR)
                send_mail(config=config, subject='AutoChronoGG: Missing token', body=MISSING_TOKEN_ERR_STR)
                return
        else:
            gg_cookie = sys.argv[1]

        results = get_web_page(POST_URL, GLOBAL_HEADERS, gg_cookie)
        if not results:
            logging.error('An unknown error occurred while fetching results. Terminating...')
            return
        elif results == ALREADY_CLICKED_CODE:
            ALREADY_CLICKED_ERR_STR = ('An error occurred while fetching results: Coin already clicked.'
                                       'Terminating...')
            logging.warning(ALREADY_CLICKED_ERR_STR)
            save_cookie(gg_cookie)
            send_mail(config=config, subject='AutoChronoGG: Coin already clicked', body=ALREADY_CLICKED_ERR_STR)
            return
        elif results == UNAUTHORIZED:
            UNAUTHORIZED_ERR_STR = ('An error occurred while fetching results: Expired/invalid authorization token.'
                                    ' Terminating...')
            logging.warning(UNAUTHORIZED_ERR_STR)
            send_mail(config=config, subject='AutoChronoGG: Invalid token', body=UNAUTHORIZED_ERR_STR)
            return
        logging.info('Done.')
        save_cookie(gg_cookie)
    except KeyboardInterrupt:
        logging.info("Interrupted.")


if __name__ == '__main__':
    with setup_logging():
        main()
