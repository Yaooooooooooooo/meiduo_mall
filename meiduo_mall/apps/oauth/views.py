from QQLoginTool.QQtool import OAuthQQ
from django import http
from django.contrib.auth import login
from django.db import DatabaseError
from django.shortcuts import render, redirect
from django.conf import settings
# Create your views here.
from django.urls import reverse
from django.views import View
import logging
import re

from carts.utils import merge_cart_cookie_to_redis
from oauth.models import OAuthQQUser
from oauth.utils import generate_access_token, check_access_token
from django_redis import get_redis_connection

from users.models import User

logger = logging.getLogger('django')

from meiduo_mall.utils.response_code import RETCODE

class QQUserView(View):

    def get(self, request):
        '''
        接收code值, 验证是否有openid, 返回结果
        :param request:
        :return:
        '''
        # 1.接收参数
        code = request.GET.get('code')

        # 2.检验
        if not code:
            return http.HttpResponseForbidden('缺少必传code')

        # 3.生成QQLoginTool对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI)

        # 4.调用对象的两个方法 ----> 获取 openid
        try:

            access_token = oauth.get_access_token(code)

            openid = oauth.get_open_id(access_token)
        except Exception as e:
            logger.error(e)

            return http.HttpResponseServerError('oauth2.0认证失败')

        # 5.判断openid是否保存到了我们的数据库中
        try:

            oauth_user = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 7.如果没有, 做另一些事
            # 7.1 把openid加密生成access_token
            access_token = generate_access_token(openid)

            # 7.2 返回access_token
            context = {
                'access_token':access_token
            }

            return render(request, 'oauth_callback.html', context=context)

        else:
            # 6.如果有, 登录成功, 返回首页
            # 6.1 状态保持:
            login(request, oauth_user.user)

            response = redirect(reverse('contents:index'))

            # 6.2 cookie
            response.set_cookie('username', oauth_user.user.username, max_age=3600 * 24 * 15)

            response = merge_cart_cookie_to_redis(request, response, oauth_user.user)

            return response

    def post(self, request):
        '''
        绑定用户发来的信息
        :param request: 
        :return: 
        '''
        # 1.接收参数(4个)
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        sms_code_client = request.POST.get('sms_code')
        access_token = request.POST.get('access_token')

        # 2.检验参数(总体检验+单个检验)
        if not all([mobile, password, sms_code_client]):
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return  http.HttpResponseForbidden('手机号格式不匹配')

        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return http.HttpResponseForbidden('密码格式不匹配')

        # redis:
        redis_conn = get_redis_connection('verify_code')

        sms_code_server = redis_conn.get('sms_code_%s' % mobile)

        if sms_code_server is None:
            return render(request, 'oauth_callback.html', {'sms_code_errmsg':'无效的短信验证码'})

        if sms_code_server.decode() != sms_code_client:
            return render(request, 'oauth_callback.html', {'sms_code_errmsg': '输入的短信验证码有误'})

        # 解密:
        openid = check_access_token(access_token)
        if openid is None:
            return render(request, 'oauth_callback.html', {'openid_errmsg': '无效的openid'})

        # 3.获取User中的用户,
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            # 4.如果没有, 往User保存
            user = User.objects.create_user(username=mobile, password=password, mobile=mobile)
        else:
            # 5.如果有, 检查密码是否正确
            if not user.check_password(password):
                return render(request, 'oauth_callback.html', {'account_errmsg': '用户名或者密码错误'})

        # 6. 保存openid和user到OAuthQQUser
        try:
            OAuthQQUser.objects.create(openid=openid, user=user)
        except DatabaseError:
            return render(request, 'oauth_callback.html', {'qq_login_errmsg': 'qq登录失败'})

        # 7. 状态保持
        login(request, user)

        # 8. 获取state值
        next = request.GET.get('state')

        response = redirect(next)

        # 9. 添加cookie
        response.set_cookie('username', user.username, max_age=3600 * 24 * 15)

        response = merge_cart_cookie_to_redis(request, response, user)

        # 10. 返回
        return response






class QQURLView(View):

    def get(self, request):
        '''
        返回qq登录的url
        :param request:
        :return:
        '''
        # 1.接收next参数
        next = request.GET.get('next')

        # 2.创建工具类的对象
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next)

        # 3.利用工具类的对象, 获取对应的qq的url
        login_url = oauth.get_qq_url()

        # 4.返回
        return http.JsonResponse({
            'code':RETCODE.OK,
            'errmsg':'ok',
            'login_url':login_url
        })
