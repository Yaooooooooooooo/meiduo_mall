from django import http
from django.shortcuts import render
from alipay import AliPay
# Create your views here.
from django.views import View
from django.conf import settings

from meiduo_mall.utils.response_code import RETCODE
from orders.models import OrderInfo
from payments.models import Payment
from users.utils import LoginRequiredJsonMixin
import os

class PaymentStatusView(View):

    def get(self, request):
        '''
        保存支付结果到数据库
        :param request:
        :return:
        '''
        # 1.获取查询字符串
        query_set = request.GET
        data = query_set.dict()

        # 2.把查询字符串中的 sign 对应的value值 剔除, 并且获取
        signature = data.pop('sign')

        # 3.获取工具类的对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),
            sign_type="RSA2",
            debug=settings.ALIPAY_DEBUG
        )

        # 4.调用对象的验证函数, 进行验证
        success = alipay.verify(data, signature)


        if success:
            # 5.如果验证成功:
            # 6.获取 trade_no  out_trade_no 值
            order_id = data.get('out_trade_no')

            trade_id = data.get('trade_no')

            # 7.保存 支付表
            Payment.objects.create(
                order_id = order_id,
                trade_id = trade_id
            )

            # 8.更改该订单状态, 返回
            OrderInfo.objects.filter(order_id=order_id,
                                     status=OrderInfo.ORDER_STATUS_ENUM['UNPAID']).update(status=OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT'])
            context = {
                'trade_id':trade_id
            }

            return render(request, 'pay_success.html', context)
        else:
            # 9.如果验证失败:
            # 10.返回结果
            return http.HttpResponseForbidden('非法请求')




class PaymentsView(LoginRequiredJsonMixin, View):

    def get(self, request, order_id):
        '''
        返回支付宝登录页面的url
        :param request:
        :param order_id:
        :return:
        '''
        # 1.检验order_id是否真的: 本用户 + 未支付状态 + 该id
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                  user=request.user,
                                  status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'])
        except Exception as e:
            return http.HttpResponseForbidden('获取订单失败')

        # 2.调用框架,创建对象
        # 创建支付宝支付对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),
            sign_type="RSA2",
            debug=settings.ALIPAY_DEBUG
        )

        # 3.调用对象的方法 ====> 查询字符串(a=1&b=2)
        # 生成登录支付宝连接
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),
            subject="美多商城%s" % order_id,
            return_url=settings.ALIPAY_RETURN_URL,
        )

        # 4.拼接url:  ip+port+路由+?+查询字符串
        alipay_url = settings.ALIPAY_URL + '?' + order_string

        # 5.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'alipay_url':alipay_url})
