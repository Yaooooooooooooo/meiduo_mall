from django import http
from django.contrib.auth import authenticate
from django.contrib.auth.backends import ModelBackend
import re

from django.contrib.auth.decorators import login_required

from meiduo_mall.utils.response_code import RETCODE
from users.models import User


def get_user_by_account(account):

    try:
        if re.match(r'^1[3-9]\d{9}$', account):
            # 手机号:
            user = User.objects.get(mobile=account)
        else:
            # 用户名:
            user = User.objects.get(username=account)
    except Exception as e:
        return None
    else:
        return user




class UsernameMobileBackendAuthentication(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        '''
        增加一个手机号验证功能
        :param request:
        :param username:
        :param password:
        :param kwargs:
        :return:
        '''

        user = get_user_by_account(username)

        if user and user.check_password(password):

            return user



class LoginRequiredMixin(object):

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view()
        return login_required(view)



from django.utils.decorators import wraps

def login_required_json(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            # 登录成功
            return view_func(request, *args, **kwargs)
        else:
            # 未登录成功
            return http.JsonResponse({'code':RETCODE.SESSIONERR,
                                      'errmsg':'用户未登录'})
    return wrapper






class LoginRequiredJsonMixin(object):

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view()
        return login_required_json(view)






