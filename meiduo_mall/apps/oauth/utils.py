from itsdangerous import TimedJSONWebSignatureSerializer
from django.conf import settings
from itsdangerous import BadData

def generate_access_token(openid):

    dict = {
        'openid':openid
    }

    serializer = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                                 expires_in=300)

    token = serializer.dumps(dict)

    return token.decode()



def check_access_token(access_token):

    serializer = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                                 expires_in=300)

    try:
        data = serializer.loads(access_token)
    except BadData:
        return None
    else:
        return data['openid']