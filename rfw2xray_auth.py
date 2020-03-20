import base64
import urlparse
from tlslite.utils import keyfactory
import oauth2 as oauth
import configparser
import constants


config = configparser.ConfigParser()


def create_oauth_client(config_file):
    try:
        global config
        #print config_file
        config.read(config_file)
        consumer = oauth.Consumer(config['DEFAULT']['CONSUMER_KEY'], config['DEFAULT']['PRIVATE_KEY'])
        accessToken = oauth.Token(config['DEFAULT']['ACCESS_TOKEN'], config['DEFAULT']['SECRET'])
        client = oauth.Client(consumer, accessToken)
        client.set_signature_method(SignatureMethod_RSA_SHA1())
        return client
    except Exception as e:
        print 'Error on OAuth: ' + e.message
        return None

class SignatureMethod_RSA_SHA1(oauth.SignatureMethod):
    name = 'RSA-SHA1'

    def signing_base(self, request, consumer, token):
        if not hasattr(request, 'normalized_url') or request.normalized_url is None:
            raise ValueError("Base URL for request is not set.")

        sig = (
            oauth.escape(request.method),
            oauth.escape(request.normalized_url),
            oauth.escape(request.get_normalized_parameters()),
        )

        key = '%s&' % oauth.escape(consumer.secret)
        if token:
            key += oauth.escape(token.secret)
        raw = '&'.join(sig)
        return key, raw

    def sign(self, request, consumer, token):
        """Builds the base signature string."""
        key, raw = self.signing_base(request, consumer, token)

        with open(config['DEFAULT']['JIRA_PRIVATE_KEY_PATH'], 'r') as f:
            data = f.read()
        privateKeyString = data.strip()

        privatekey = keyfactory.parsePrivateKey(privateKeyString)
        signature = privatekey.hashAndSign(raw)

        return base64.b64encode(signature)