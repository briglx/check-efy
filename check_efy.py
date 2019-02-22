#!/usr/bin/env python3
"""Script to Check EFY for availibility."""
from urllib.request import urlopen
from bs4 import BeautifulSoup
import time
import numpy as np
import logging
import os
import sys
from twilio.rest import Client
import argparse
import re

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = 'check-efy.log'
SESSION_ID = "UT Provo 04B"

MSG_UNAVAILABLE = "%s. No spots left for %s on %s"
MSG_AVAILABLE = "%s spots left for %s on %s"
MSG_TEXT_MESSAGE = ("%s spots availible for session %s at efy." +
                    "Click here https://efy.byu.edu/efy_session/10091862.")
MSG_RECIPIENT_ERR = ("Invalid recipient number %s" +
                     ". Recipient should be formatted with a '+' " +
                     "and country code e.g., +16175551212 (E.164 format).")


def setup_logger(log_file, verbose=False):
    """Set up the logging.

    Parameters
    ----------
    log_file : string
                path to a log file
    verbose : bool
                set's the default log level to INFO. Default is False.

    """
    fmt = ("%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(format=fmt, datefmt=datefmt, level=logging.INFO)

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('twilio.http_client').setLevel(logging.WARNING)

    # Log errors to a file if we have write access to file or config dir
    if log_file is None:
        err_log_path = os.path.abspath(ERROR_LOG_FILENAME)
    else:
        err_log_path = os.path.abspath(log_file)

    err_path_exists = os.path.isfile(err_log_path)
    err_dir = os.path.dirname(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(err_dir, os.W_OK)):

        err_handler = logging.FileHandler(
            err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    logger = logging.getLogger('')
    logger.addHandler(err_handler)
    logger.setLevel(logging.INFO)


def isSiteAvailable(session_id):
    """Check if site is available.

    Parameters
    ----------
    session_id : string
                EFY formated session as UT Provo 04B.

    """
    url = "https://efy.byu.edu/available-sessions"

    _LOGGER.info("Checking availibility for session %s", session_id)

    try:
        f = urlopen(url)
        soup = BeautifulSoup(f, 'html.parser')
        table = soup.find('table', attrs={'id': 'efySchedule'})
        table_body = table.find('tbody')
        rows = table_body.find_all('tr')
        for row in rows:
            cols = row.find_all('td')

            cols = [ele.text.strip() for ele in cols]

            c_session_id = cols[0]
            c_session_date = cols[1]
            c_seats = cols[3]

            if c_session_id == session_id:

                if c_seats == 'Full':
                    _LOGGER.info(MSG_UNAVAILABLE, c_seats,
                                 session_id, c_session_date)
                    return (0, False)

                else:
                    _LOGGER.info(MSG_AVAILABLE, c_seats,
                                 session_id, c_session_date)

                return (c_seats, True)

    except ConnectionResetError:

        _LOGGER.error("Connection closed ... try again.")

        return (0, False)


def get_delay_mins(mu=10, sigma=15):
    """Generate random value for delay mins.

    Generates a random number around mu with sigma
    standard deviation. The number will never be negative.

    Parameters
    ----------
    mu : int
            mean. Default 10.
    sigma: int
            standard deviation. Default 15.

    """
    x = np.random.normal(mu, sigma)

    if x < 0:
        x = 0

    return int(x)


def delay_with_update_by_min(mins):
    """Delay execution and log updates.

    Parameters
    ----------
    mins : int
            Number of minutes to delay.

    """
    _LOGGER.info("Waiting " + str(mins) + " mins")
    for i in range(mins):
        time.sleep(60)


def sendMessage(client, msg, sender, recipient):
    """Send message via text.

    Parameters
    ----------
    client : obj
            twilio client.
    msg : str
            message to send via text.
    sender: str
            The source phone number for SMS/MMS
            formatted with a '+' and country code e.g.,
            +16175551212 (E.164 format).
    recipient: str
            The destination phone number for SMS/MMS
            formatted with a '+' and country code e.g.,
            +16175551212 (E.164 format).

    """
    message = client.messages \
                    .create(
                        body=msg,
                        from_=sender,
                        to=recipient
                    )

    _LOGGER.info("Sent message " + message.sid)


def get_arguments():
    """Parse system arguments."""
    parser = argparse.ArgumentParser(
        prog="Check Efy.",
        description="Check Efy.")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')
    parser.add_argument('recipients', nargs='+',
                        metavar='recipients',
                        help='List of recipients to recieve text messages.')
    parser.add_argument('--sender', nargs='+',
                        help='The text message sender number.')
    parser.add_argument('--account-id', nargs='+',
                        help='Twilio account id used to send text messages.')
    parser.add_argument('--auth-token', nargs='+',
                        help='Twilio auth-token used to send text messages.')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Enable verbose logging to file")
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='Log file to write to.  If not set, ' + ERROR_LOG_FILENAME +
             ' is used')

    arguments = parser.parse_args()
    return arguments


def validate_e164(recipients):
    """Validate recipient number.

    Parameters
    ----------
    recipients: array of str
            The destination phone number for SMS/MMS
            formatted with a '+' and country code e.g.,
            +16175551212 (E.164 format).

    """
    for recipient in recipients:
        found = bool(re.match(r"^\+[1-9]\d{1,14}$", recipient))
        if not found:
            raise ValueError(MSG_RECIPIENT_ERR % recipient)


def main():
    """Kick off script."""
    try:

        args = get_arguments()
        setup_logger(args.log_file, args.verbose)
        sender = args.sender
        recipients = args.recipients
        validate_e164(recipients + sender)
        client = Client(args.account_id, args.auth_token)

        while True:
            try:
                (spots, available) = isSiteAvailable(SESSION_ID)

                if available:
                    for recipient in recipients:
                        message = MSG_TEXT_MESSAGE % str(spots),  SESSION_ID
                        sendMessage(client, message, sender, recipient)

                delay_mins = get_delay_mins()
                delay_with_update_by_min(delay_mins)

            except KeyboardInterrupt as kerr:
                _LOGGER.info(kerr)
                sys.exit(0)

    except ValueError as err:
        print("Value error: {0}".format(err))

    sys.exit(0)


if __name__ == "__main__":
    print("Starting Check Efy Script.")
    sys.exit(main())
