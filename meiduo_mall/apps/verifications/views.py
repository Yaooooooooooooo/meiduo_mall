from django import http
from django.shortcuts import render
import random
# Create your views here.
from django.views import View
from django_redis import get_redis_connection
from meiduo_mall.libs.captcha.captcha import captcha
from meiduo_mall.libs.yuntongxun.ccp_sms import CCP
from meiduo_mall.utils.response_code import RETCODE
from . import crons
import logging
logger = logging.getLogger('django')



class SMSCodeView(View):

    def get(self, request, mobile):
        '''
        接收参数, 发送短信验证码给手机
        :param request:
        :param mobile:
        :return:
        '''
        # 0. 获取redis中保存60的值
        # 3.链接redis
        redis_conn = get_redis_connection('verify_code')
        sms_flag = redis_conn.get('sms_flag_%s' % mobile)
        if sms_flag:
            # 60s没过
            return http.HttpResponseForbidden('不要频发发送短信验证码')

        # 1.接收参数(图片验证码, uuid)
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('image_code_id')

        # 2.校验
        if not all([image_code_client, uuid]):
            return http.HttpResponseForbidden('缺少必传参数')

        # 4.从redis中获取图形验证码
        image_code_server = redis_conn.get('img_%s' % uuid)

        # 5.判断提取出来的是否存在, 如果不存在说明过期
        if image_code_server is None:
            return http.JsonResponse({'code':RETCODE.IMAGECODEERR,
                                      'errmsg':'图形验证码过期'})

        # 6.删除图形验证码
        try:
            redis_conn.delete('img_%s' % uuid)
        except Exception as e:
            logger.error(e)

        # 7.对比图形验证码
        if image_code_client.lower() != image_code_server.decode().lower():
            return http.JsonResponse({'code':RETCODE.IMAGECODEERR,
                                      'errmsg':'输入的图形验证码有误'})

        # 8. 生成短信验证码
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info(sms_code)

        # 获取管道对象
        pl = redis_conn.pipeline()

        # 9. 保存到redis
        pl.setex('sms_code_%s' % mobile, 300, sms_code)
        pl.setex('sms_flag_%s' % mobile, 60, 1)

        # 执行管道
        pl.execute()

        # 10.发送短信验证码给对应的手机
        # CCP().send_template_sms(mobile, [sms_code, 5], 1)

        from celery_tasks.sms.tasks import send_sms_code
        send_sms_code.delay(mobile, sms_code)

        # 11.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok'})


class ImageCodeView(View):

    def get(self, request, uuid):
        '''
        返回注册页面的图形验证码
        :param request:
        :param uuid:
        :return:
        '''
        # 1.生成图形验证码
        text, image = captcha.generate_captcha()

        # 2.链接redis, 获取一个链接对象
        redis_conn = get_redis_connection('verify_code')

        # 3.使用链接对象, 保存数据到redis
        redis_conn.setex('img_%s' % uuid, crons.NUM_VERIFY_SMS_CODE, text)

        # 4.返回(图片)
        return http.HttpResponse(image, content_type='image/jpg')