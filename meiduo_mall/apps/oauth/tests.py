from django.test import TestCase
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meiduo_mall.settings.dev")

from itsdangerous import TimedJSONWebSignatureSerializer
from django.conf import settings

# Create your tests here.
if __name__ == '__main__':

    dict = {
        'openid':'sdfjjdfoijofjo'
    }

    serialier = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                    expires_in=300)


    token = serialier.dumps(dict).decode()
    print(token)


    data = serialier.loads(token)
    print(data)
