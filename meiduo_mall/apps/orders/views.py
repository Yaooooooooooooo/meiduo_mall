import json
from decimal import Decimal

from django import http
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import render

# Create your views here.
from django.utils import timezone
from django.views import View
from django_redis import get_redis_connection

from goods.models import SKU
from meiduo_mall.utils.response_code import RETCODE
from orders.models import OrderInfo, OrderGoods
from users.models import Address
from users.utils import LoginRequiredMixin, LoginRequiredJsonMixin


class UserOrderInfoView(LoginRequiredMixin, View):
    
    def get(self, request, page_num):
        '''
        展示我的订单页面
        :param request: 
        :param page_num: 
        :return: 
        '''
        user = request.user
        # 1.查询当前用户的所有订单
        orders = user.orderinfo_set.all().order_by('-create_time')

        # 2.遍历所有订单, 拿到每一个
        for order in orders:
            # 3.绑定订单属性: status_name
            order.status_name = OrderInfo.ORDER_STATUS_CHOICES[order.status - 1][1]

            # 4.绑定订单属性: pay_method_name
            order.pay_method_name = OrderInfo.PAY_METHOD_CHOICES[order.pay_method - 1][1]

            # 9.1创建订单列表
            order.sku_list = []

            # 5.获取订单对应的所有商品行
            order_goods = order.skus.all()

            # 6.遍历商品行, 获取每一行商品
            for order_good in order_goods:
                # 7.获取商品
                sku = order_good.sku

                # 8.给商品绑定 count amount
                sku.count = order_good.count
                sku.amount = order_good.count * sku.price

                # 9.把商品添加到 订单的列表中
                order.sku_list.append(sku)

                page_num = int(page_num)
                # 10. 创建一个分页对象
                paginator = Paginator(orders, 1)
                try:
                    # 11. 获取对应页面的订单数据
                    page_orders = paginator.page(page_num)
                    # 12. 获取所有的订单页数
                    total_page = paginator.num_pages
                except Exception as e:
                    return http.HttpResponseForbidden('缺少对应的页面')

                # 13. 拼接参数
                context = {
                    'page_num':page_num,
                    'page_orders':page_orders,
                    'total_page':total_page
                }

                # 14. 返回
                return render(request, 'user_center_order.html', context)





class OrderSuccessView(LoginRequiredMixin, View):

    def get(self, request):
        '''
        返回订单提交成功页面
        :param request:
        :return:
        '''
        # 1.获取查询字符串的数据
        order_id = request.GET.get('order_id')
        payment_amount = request.GET.get('payment_amount')
        pay_method = request.GET.get('pay_method')


        # 2.拼接
        context = {
            'order_id':order_id,
            'payment_amount':payment_amount,
            'pay_method':pay_method
        }
        # 3.返回
        return render(request, 'order_success.html', context)



class OrderSettlementView(LoginRequiredMixin, View):

    def get(self, request):
        '''
        返回订单页面
        :param request:
        :return:
        '''
        # 1.获取当前用户的没有删除的所有地址
        try:
            addresses = Address.objects.filter(user=request.user,
                                   is_deleted=False)

        except Exception as e:
            addresses = None

        # 2.链接redis
        redis_conn = get_redis_connection('carts')

        # 3.从hash取值:  user_id : {sku_id : count}
        item_dict = redis_conn.hgetall('carts_%s' % request.user.id)

        # 4.从set取值 # user_id: {sku_id1, ...}
        selected_carts = redis_conn.smembers('selected_%s' % request.user.id)

        dict = {}
        # 5.遍历set的数据, 取出sku_id=====> 去hash的数据中获取:count
        for sku_id in selected_carts:
            # 6.拼接数据
            dict[int(sku_id)] =  int(item_dict[sku_id])

        # 7.根据id, 获取所有的商品sku
        skus = SKU.objects.filter(id__in=dict.keys())


        total_count = 0
        total_amount = Decimal('0.00')

        # 8.遍历所有的商品, 取出每一个 ===> 增加属性: count amount
        for sku in skus:
            sku.count = dict.get(sku.id)
            sku.amount = sku.price * sku.count

            # 9. 把count 和 amount 累加到变量上
            total_count += sku.count
            total_amount += sku.amount

        # 指定运费
        freight = Decimal('10.00')

        # 拼接参数
        context = {
            'addresses':addresses,
            'skus':skus,
            'total_count':total_count,
            'total_amount':total_amount,
            'freight':freight,
            'payment_amount':total_amount + freight
        }

        # 返回
        return render(request, 'place_order.html', context=context)


class OrderCommitView(LoginRequiredJsonMixin, View):

    def post(self, request):
        '''
        保存订单信息
        :param request:
        :return:
        '''
        # 1 获取参数
        json_dict = json.loads(request.body.decode())
        address_id = json_dict.get('address_id')
        pay_method = json_dict.get('pay_method')

        # 2. 检验(整体  单个)
        if not all([address_id, pay_method]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            address = Address.objects.get(id=address_id)
        except Exception as e:
            return http.HttpResponseForbidden('address_id有误')

        if pay_method not in [OrderInfo.PAY_METHODS_ENUM['CASH'], OrderInfo.PAY_METHODS_ENUM['ALIPAY']]:
            return http.HttpResponseForbidden('pay_method有误')

        # 3.2 获取用户
        user = request.user

        # 3.1 生成order_id:
        order_id = timezone.localtime().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)

        with transaction.atomic():

            save_id = transaction.savepoint()

            # 3.保存订单:OrderInfo
            order = OrderInfo.objects.create(
                order_id = order_id,
                user = user,
                address = address,
                total_count = 0,
                total_amount=Decimal('0.00'),
                freight=Decimal('10.00'),
                pay_method = pay_method,
                # status =  值1 if 条件成立 else 值2
                status = OrderInfo.ORDER_STATUS_ENUM['UNPAID'] if pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY'] else OrderInfo.ORDER_STATUS_ENUM['UNSEND']
            )
            # 4.链接redis
            redis_conn = get_redis_connection('carts')

            # 5.从hash取值
            item_dict = redis_conn.hgetall('carts_%s' % user.id)

            # 6.从set中取值
            selected_carts = redis_conn.smembers('selected_%s' % user.id)

            dict = {}
            # 7.把 hash 中的 count 和 set 中的sku_id 放到一起 dict
            for sku_id in selected_carts:
                dict[int(sku_id)] = int(item_dict.get(sku_id))

            # 8.获取所有的商品id
            sku_ids = dict.keys()

            # 9.遍历每一个商品id ===> 获取对应的sku
            for sku_id in sku_ids:

                while True:
                    # 商品
                    sku = SKU.objects.get(id=sku_id)
                    # 销量:
                    sku_count = dict.get(sku.id)

                    origin_stock = sku.stock
                    origin_sales = sku.sales

                    # 10.判断当前商品的库存是否大于销售量
                    if sku.stock < sku_count:
                        transaction.savepoint_rollback(save_id)
                        return http.JsonResponse({'code':RETCODE.STOCKERR,
                                                  'errmsg':'库存不足'})

                    # import time
                    # time.sleep(5)

                    # 11. 修改商品表sku:  销量和库存量
                    # sku.stock -= sku_count
                    # sku.sales += sku_count
                    # sku.save()

                    new_stock = origin_stock - sku_count
                    new_sales = origin_sales + sku_count

                    result = SKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)

                    if result == 0:
                        continue



                    # 12. 修改商品类别的销量: 销量改变
                    sku.goods.sales += sku_count
                    sku.goods.save()

                    # 13. 保存到订到商品表中
                    OrderGoods.objects.create(
                        order = order,
                        sku = sku,
                        count = sku_count,
                        price = sku.price
                    )

                    # 14. 订单表中的对应字段要改变: 总数量 + 总价格
                    order.total_count += sku_count
                    order.total_amount += sku_count * sku.price
                    # 事务提交:
                    transaction.savepoint_commit(save_id)
                    break

        # 累加运费:
        order.total_amount += order.freight
        order.save()

        # 15.删除购物车对应的数据
        redis_conn.hdel('carts_%s' % user.id, *selected_carts)

        redis_conn.srem('selected_%s' % user.id, *selected_carts)

        # 16.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'order_id':order_id})