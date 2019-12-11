from django import http
from django.contrib.auth import login, authenticate, logout
from django.db import DatabaseError
from django.shortcuts import render, redirect
import re
# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection
from areas.models import Area
from carts.utils import merge_cart_cookie_to_redis
# from goods.models import SKU

from meiduo_mall.utils.response_code import RETCODE
from users.models import User, Address
from users.utils import LoginRequiredMixin, LoginRequiredJsonMixin
import json
import logging

logger = logging.getLogger('django')


class UserBrowserHistory(LoginRequiredJsonMixin, View):

    def get(self, request):
        '''
        获取reids中的用户浏览记录, 返回
        :param request:
        :return:
        '''
        # 1.链接redis
        redis_conn = get_redis_connection('history')
        # 2.获取数据
        sku_ids = redis_conn.lrange('history_%s' % request.user.id, 0, -1)

        skus = []

        # 3.遍历整理格式
        for sku_id in sku_ids:
            sku = SKU.objects.get(id=sku_id)
            skus.append({
                'id':sku.id,
                'name':sku.name,
                'default_image_url':sku.default_image_url,
                'price':sku.price
            })

        # 4.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'skus':skus})



    def post(self, request):
        '''
        保存用户浏览记录
        :param request:
        :return:
        '''
        # 1.接收参数(json)
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        # 2.校验(sku_id)
        try:
            SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden("缺少必传参数")

        # 3.链接redis
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()
        user_id = request.user.id

        # 4.保存到redis
        # 4.1 去重 4.2 保存 4.3 截串
        pl.lrem('history_%s' % user_id, 0, sku_id)
        pl.lpush('history_%s' % user_id, sku_id)
        pl.ltrim('history_%s' % user_id, 0, 4)

        # 4.4 执行管道:
        pl.execute()

        # 5.返回(json)
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok'})







class ChangePasswordView(LoginRequiredMixin, View):

    def get(self, request):
        '''
        提供修改密码页面
        :param request:
        :return:
        '''
        return render(request, 'user_center_pass.html')

    def post(self, request):
        '''
        修改密码
        :param request:
        :return:
        '''
        # 1.接收参数
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')

        # 2.校验(整体 + 先检验老密码 ===> 新密码检验)
        if not all([old_password, new_password2, new_password]):
            return http.HttpResponseForbidden("缺少必传参数")

        try:
            # 先检验老密码: check_password()
            result = request.user.check_password(old_password)
        except Exception as e:
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg':'原始密码错误'})

        if not result:
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg':'原始密码错误'})


        # 新密码检验
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', new_password):
            return http.HttpResponseForbidden('新密码不符合格式')

        if new_password != new_password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 3.把新密码设置, 保存
        try:
            request.user.set_password(new_password)
            request.user.save()
        except Exception as e:
            return render(request, 'user_center_pass.html', {'change_pwd_errmsg':'更改密码出错'})

        # 4.清除状态(session + cookie)
        logout(request)

        response = redirect(reverse('users:login'))

        response.delete_cookie('username')

        # 5.返回
        return response






class UpdateTitleAddressView(LoginRequiredJsonMixin, View):

    def put(self, request, address_id):
        '''
        修改该地址的标题
        :param request:
        :param address_id:
        :return:
        '''
        # 1.接收参数(json)
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')

        # 2.根据address_id 取地址
        try:
            address = Address.objects.get(id=address_id)

            # 3.修改该地址的标题
            address.title = title
            # 4.保存
            address.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '修改地址标题出错'})

        # 5.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok'})


class DefaultAddressView(LoginRequiredJsonMixin, View):
    def put(self, request, address_id):
        '''
        设置默认地址
        :param request:
        :param address_id:
        :return:
        '''
        # 1.根据id, 获取对应的地址
        try:
            address = Address.objects.get(id=address_id)

            # 2.把该地址赋值给 原来的默认地址(request.user.default_address)
            request.user.default_address = address
            # 3.保存
            request.user.save()

        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '数据库更新出错'})

        # 4.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok'})


class UpdateDestroyAddressView(LoginRequiredJsonMixin, View):

    def put(self, request, address_id):
        '''
        接收前端传入的参数, 修改数据库数据, 返回
        :param request:
        :param address_id:
        :return:
        '''
        # 1.接收参数(json)
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 2.校验(整体 + 单个)
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('手机号格式不正确')

        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('固定电话格式不正确')

        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('email格式不正确')

        # 3.修改数据库数据
        try:
            result = Address.objects.filter(id=address_id).update(
                user=request.user,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                title=receiver,
                receiver=receiver,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except Exception as  e:
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '修改数据库出错'})

        # print(result)

        address = Address.objects.get(id=address_id)

        # 4.拼接参数, 准备返回
        address_dict = {
            'id': address.id,
            'receiver': address.receiver,
            'province': address.province.name,
            'city': address.city.name,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 5.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'address': address_dict})

    def delete(self, request, address_id):
        '''
        删除对应的地址(逻辑删除)
        :param request:
        :param address_id:
        :return:
        '''
        # 1.根据address_id获取对应的地址
        try:
            address = Address.objects.get(id=address_id)

            # 2.修改地址的is_deleted为True
            address.is_deleted = True
            # 3.保存
            address.save()
        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '删除数据库出错'})

        # 4.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok'})


class CreateAddressView(LoginRequiredJsonMixin, View):

    def post(self, request):
        '''
        接收参数, 保存到mysql中, 新增地址
        :param request:
        :return:
        '''
        # 1.判断数据库中是否已经有20个地址了
        # count = request.user.addresses.count()
        # count = request.user.addresses.model.objects.filter(is_deleted=False).count()
        count = request.user.addresses.filter(is_deleted=False).count()
        if count >= 20:
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR,
                                      'errmsg': '超过地址上限'})

        # 2.接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 3.校验(整体 + 单个)
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'', mobile):
            return http.HttpResponseForbidden('手机号不符合规定')

        if tel:
            if not re.match(r'', tel):
                return http.HttpResponseForbidden('固定电话不符合规定')

        if email:
            if not re.match(r'', email):
                return http.HttpResponseForbidden('email不符合规定')

        province = Area.objects.get(id=province_id)

        try:
            address = Address.objects.create(
                user=request.user,
                province=province,
                city_id=city_id,
                district_id=district_id,
                title=receiver,
                receiver=receiver,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )

            # 4.判断是否有默认地址, 如果没有, 把当前地址作为默认地址
            if not request.user.default_address:
                request.user.default_address = address
                request.user.save()
        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR,
                                      'errmsg': '保存地址出错'})

        # 5.拼接参数, 准备返回
        address_dict = {
            'id': address.id,
            'receiver': address.receiver,
            'province': address.province.name,
            'city': address.city.name,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 6.返回
        return http.JsonResponse({'code': RETCODE.OK,
                                  'errmsg': 'ok',
                                  'address': address_dict})


class AddressView(LoginRequiredMixin, View):

    def get(self, request):
        '''
        返回地址页面
        :param request:
        :return:
        '''
        # 1.获取所有的地址: 当前用户+没有删除
        addresses = Address.objects.filter(user=request.user, is_deleted=False)

        address_model_list = []

        # 2.遍历, 获取每一个地址
        for address in addresses:

            # 3.拼接参数(dict)
            address_dict = {
                'id': address.id,
                'receiver': address.receiver,
                'province': address.province.name,
                'city': address.city.name,
                'district': address.district.name,
                'place': address.place,
                'mobile': address.mobile,
                'tel': address.tel,
                'email': address.email,
                'title': address.receiver
            }
            # 4.判断当前地址是否是默认地址
            if request.user.default_address.id == address.id:
                # 5.如果是, 放到列表的第一个位置
                address_model_list.insert(0, address_dict)
            else:
                # 6.如果不是, 后面追加
                address_model_list.append(address_dict)

        # 7.拼接参数
        context = {
            'default_address_id': request.user.default_address_id,
            'addresses': address_model_list
        }
        # 8.返回
        return render(request, 'user_center_site.html', context=context)


class VerifyEmailView(View):

    def get(self, request):
        '''
        验证邮箱是否有效(是否激活)
        :param request: 
        :return: 
        '''
        # 1.接受参数
        token = request.GET.get('token')

        # 2.校验
        if not token:
            return http.HttpResponseForbidden('缺少必传参数')

        # 3.解密
        user = User.check_verify_token(token)

        if not user:
            return http.HttpResponseForbidden('无效的token')

        # 4.修改记录
        try:
            user.email_active = True
            user.save()
        except Exception as e:
            return http.HttpResponseForbidden('修改失败')

        # 5.返回(用户中心)
        return redirect(reverse('users:info'))


class EmailView(LoginRequiredJsonMixin, View):

    def put(self, request):
        '''
        接收email,更新到数据库中
        :param request:
        :return:
        '''
        # 1.接收参数
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')

        # 2.校验
        if not email:
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return http.HttpResponseForbidden('email格式不争取')

        # 3.更新
        try:
            request.user.email = email
            request.user.save()
        except Exception as e:
            logger.error(e)

            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '写入数据库出错'})

        # 发送邮件:
        from celery_tasks.email.tasks import send_verify_email
        verify_url = request.user.generate_verify_email_url()
        send_verify_email.delay(email, verify_url)

        # 4.返回
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'ok'})


class UserInfoView(LoginRequiredMixin, View):

    def get(self, request):
        '''
        返回用户中心页面
        :param request:
        :return:
        '''

        # if request.user.is_authenticated:
        #     return render(request, 'user_center_info.html')
        # else:
        #     return http.HttpResponseForbidden('你没有登录')

        context = {
            'username': request.user.username,
            'mobile': request.user.mobile,
            'email': request.user.email,
            'email_active': request.user.email_active
        }

        return render(request, 'user_center_info.html', context)


class LogoutView(View):
    def get(self, request):
        '''
        退出登录
        :param request:
        :return:
        '''
        # 1.清理session
        logout(request)

        # 2.获取response对象
        response = redirect(reverse('contents:index'))

        # 3.使用response对象, 删除cookie
        response.delete_cookie('username')

        # 4.返回
        return response


class LoginView(View):

    def post(self, request):
        '''
        接收参数, 检验参数, 决定用户是否登录成功
        :param request:
        :return:
        '''
        # 1.接受参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        remembered = request.POST.get('remembered')

        # 2.校验(全局 + 单个)
        if not all([username, password]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 单个检验
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('用户名不符合5-20位的格式')

        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return http.HttpResponseForbidden('密码不符合8-20位的格式')

        # 3.认证用户是否登录
        user = authenticate(username=username, password=password)

        # 4.如果没有当前用户, 报错
        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})

        # 5.设置状态保持
        login(request, user)

        # 6.判断是否记住登录状态
        if remembered != 'on':
            # 没有勾选:
            request.session.set_expiry(0)
        else:
            # 勾选状态: None: 两周
            request.session.set_expiry(None)

        next = request.GET.get('next')  # /info/

        if next:
            response = redirect(next)

        else:
            response = redirect(reverse('contents:index'))

        response.set_cookie('username', user.username, max_age=3600 * 24 * 15)

        response = merge_cart_cookie_to_redis(request, response, user)

        # 7.重定向到首页
        return response

    def get(self, request):
        '''
        返回登录页面
        :param request:
        :return:
        '''
        return render(request, 'login.html')


class MobileCountView(View):

    def get(self, request, mobile):
        '''
        检验手机号是否重复: 把接收的手机号扔到mysql查询,返回结果
        :param request:
        :param username:
        :return:
        '''
        # 1.mysql查询mobile对应的个数
        count = User.objects.filter(mobile=mobile).count()

        # 2.返回
        return http.JsonResponse({
            'code': RETCODE.OK,
            'errmsg': 'ok',
            'count': count
        })


class UsernameCountView(View):

    def get(self, request, username):
        '''
        检验用户名是否重复: 把接收的用户名扔到mysql查询,返回结果
        :param request:
        :param username:
        :return:
        '''
        # 1.mysql查询username对应的个数
        count = User.objects.filter(username=username).count()

        # 2.返回
        return http.JsonResponse({
            'code': RETCODE.OK,
            'errmsg': 'ok',
            'count': count
        })


class RegisterView(View):

    def post(self, request):
        '''
        接收用户发过来的注册信息, 保存到mysql
        :param request:
        :return:
        '''
        # 1.接收参数
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        mobile = request.POST.get('mobile')
        allow = request.POST.get('allow')
        sms_code_client = request.POST.get('sms_code')

        # 2.检验参数(总体检验 + 单个检验)
        if not all([username, password, password2, mobile, allow]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 单个检验
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('用户名不符合5-20位的格式')

        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return http.HttpResponseForbidden('密码不符合8-20位的格式')

        if password != password2:
            return http.HttpResponseForbidden('两次输入密码不一致')

        if not re.match(r'^1[3456789]\d{9}$', mobile):
            return http.HttpResponseForbidden('手机号不符合')

        if allow != 'on':
            return http.HttpResponseForbidden('请勾选用户协议')

        # 2.1 链接redis
        redis_conn = get_redis_connection('verify_code')

        # 2.2 获取redis中的短信验证码
        sms_code_server = redis_conn.get('sms_code_%s' % mobile)
        if sms_code_server is None:
            return render(request, 'register.html', {'sms_code_errmsg': '无效的短信验证码'})

        # 2.3 判断两个验证码是否一致
        if sms_code_server.decode() != sms_code_client:
            return render(request, 'register.html', {'sms_code_errmsg': '前端输入的短信验证码有误'})

        # 3.往mysql存(User)
        try:
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except DatabaseError:

            return render(request, 'register.html', {'register_errmsg': '保存数据失败'})

        # 保持状态:
        login(request, user)

        response = redirect(reverse('contents:index'))

        # 往cookie中写入username
        response.set_cookie('username', user.username, max_age=3600 * 24 * 15)

        # 4.返回结果
        # return http.HttpResponse('保存成功,跳转到首页')
        return response

    def get(self, request):
        '''
        返回register.html(注册页面)
        :param request:
        :return:
        '''
        return render(request, 'register.html')
