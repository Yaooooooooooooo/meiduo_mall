import base64
import json
import pickle
from django import http
from django.contrib.auth import login
from django.shortcuts import render
from django_redis import get_redis_connection
# Create your views here.
from django.views import View
from goods.models import SKU
from meiduo_mall.utils.response_code import RETCODE


class CartsSimpleView(View):

    def get(self, request):
        '''
        展示首页等, 小的商品购物车数据
        :param request:
        :return:
        '''
        # 1.判断用户是否登录
        if request.user.is_authenticated:

            # 2.如果登录:
            # 3.链接redis
            redis_conn = get_redis_connection('carts')

            # 4.从hash中取值
            item_dict = redis_conn.hgetall('carts_%s' % request.user.id)

            # 5.从set表中取值
            selected_carts = redis_conn.smembers('selected_%s' % request.user.id)

            cart_dict = {}

            # 6.拼接整理格式 ===> cookie:   cart_dict = {sku_id : {'count':2, 'selected':True }}
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {
                    'count':int(count),
                    'selected': sku_id in selected_carts
                }
        else:
            # 7.如果未登录:
            # 8.从cookie取值
            cookie_cart = request.COOKIES.get('carts')

            # 9.判断是否有值
            if cookie_cart:

                # 10.如果有值, 解密
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 11. 如果没有值, 新建字典
                cart_dict = {}

        # 12.共同完成:
        # 13. 获取字典中的所有的商品id
        sku_ids = cart_dict.keys()

        # 14. 根据所有的商品id, 获取所有的商品
        skus = SKU.objects.filter(id__in=sku_ids)

        list = []
        # 15. 遍历所有的商品, 获取每一个
        for sku in skus:

            # 16. 拼接格式
            list.append({
                "id": sku.id,
                "name": sku.name,
                "count": cart_dict.get(sku.id).get('count'),
                "default_image_url":sku.default_image_url
            })

        # 17. 返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'cart_skus':list})



class CartSelectAllView(View):

    def put(self, request):
        '''
        修改购物车的是否全选状态
        :param request:
        :return:
        '''
        # 1.接收参数(selected)
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected')

        # 2.检验
        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('seleced有误')

        # 3.判断是否登录
        if request.user.is_authenticated:

            # 4.如果登录:
            # 5.链接redis
            redis_conn = get_redis_connection('carts')

            # 6.从hash中取出所有的商品的id
            # hash: carts_user_id : {sku_id: count}
            item_dict = redis_conn.hgetall('carts_%s' % request.user.id)
            sku_ids = item_dict.keys()

            # 7.判断是否是全选, 如果是全选: 把所有的id写入到set表中
            if selected:
                redis_conn.sadd('selected_%s' % request.user.id, *sku_ids)
            else:
                # 8.如果是全不选, 把set中的对应的id数据删掉
                redis_conn.srem('selected_%s' % request.user.id, *sku_ids)

            # 9. 返回:
            return http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok'})
        else:
            # 1.获取cookie值
            cookie_cart = request.COOKIES.get('carts')

            response = http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok'})

            # 2.判断该值是否存在
            if cookie_cart:
                # 3.如果存在, 解密
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))

                # 4.获取字典中的所有的keys
                sku_ids = cart_dict.keys()

                # 5.遍历, 获取单个的key
                # cookie:    sku_id : { 'count': 1, 'selected': True}
                for sku_id in sku_ids:
                    # 6.更改
                    cart_dict[sku_id]['selected'] = selected

                # 7.加密
                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()
                # 8.保存到cookie
                response.set_cookie('carts', cart_data)

            # 9.返回
            return response

class CartsView(View):

    def delete(self, request):
        '''
        删除购物车数据
        :param request:
        :return:
        '''
        # 1.接收参数(sku_id)
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')


        # 2.检验
        try:
            SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden('缺少必传参数')

        # 3.判断是否登录
        if request.user.is_authenticated:

            # 4.如果登录,链接redis
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()

            # 5.hash表中删除
            pl.hdel('carts_%s' % request.user.id, sku_id)
            # 6.set表中删除
            pl.srem('selected_%s' % request.user.id, sku_id)

            pl.execute()

            # 7.返回
            return http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok'})
        else:
            # 8.如果未登录, 从cookie中获取数据
            cookie_cart = request.COOKIES.get('carts')

            # 9.判断数据是否存在,
            if cookie_cart:

                # 10.如果存在, 解密
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 11. 如果不存在, 创建新的
                cart_dict = {}

            response = http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok'})

            # 12. 判断sku_id是否在字典中
            if sku_id in cart_dict:

                # 13. 删除
                del cart_dict[sku_id]

                # 14. 把未删除的数据加密
                cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

                # 15. 写入cookie
                response.set_cookie('carts', cart_data)

            # 16. 返回
            return response


    def put(self, request):
        '''
        修改购物车数据
        :param request:
        :return:
        '''
        # 1.接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected')


        # 2.检验(整体 + 局部)
        if not all([sku_id, count]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden('sku_id参数有误')

        try:
            count = int(count)
        except Exception as e:
            return http.HttpResponseForbidden('count参数有误')

        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('selected参数有误')

        # 3.判断是否登录
        if request.user.is_authenticated:
            # 登录用户:
            # 4. 链接redis
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()

            # 5. 修改hash表
            pl.hset('carts_%s' % request.user.id, sku_id, count)

            # 6. 修改set: 如果为真: 添加  如果为假: 要移出
            if selected:
                pl.sadd('selected_%s' % request.user.id, sku_id)
            else:
                pl.srem('selected_%s' % request.user.id, sku_id)

            pl.execute()

            # 7. 拼接数据
            dict = {
                'id': sku.id,
                'name': sku.name,
                'default_image_url': sku.default_image_url,
                'count': count,
                'price': sku.price,
                'amount': str(sku.price * count),
                'selected': selected
            }

            # 8. 返回
            return http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok',
                                      'cart_sku':dict})
        else:
            # 未登录:
            # 1.获取cookie中的数据
            cookie_cart = request.COOKIES.get('carts')

            # 2.判断数据是否存在
            if cookie_cart:

                # 3.如果存在:  解密
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 4.如果不存在, 新建
                cart_dict = {}

            # 5.把新数据修改到字典中
            cart_dict[sku_id] = {
                'count':count,
                'selected':selected
            }
            # 6.加密
            cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

            # 7.拼接数据
            dict = {
                'id': sku.id,
                'name': sku.name,
                'default_image_url': sku.default_image_url,
                'count': count,
                'price': sku.price,
                'amount': str(sku.price * count),
                'selected': selected
            }

            response = http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok',
                                      'cart_sku':dict})

            # 8.写入到cookie中
            response.set_cookie('carts', cart_data)

            # 9.返回
            return response


    def get(self, request):
        '''
        展示购车页面
        :param request:
        :return:
        '''
        # 1.判断用户是否登录
        if request.user.is_authenticated:

            # 2.如果登录:
            # 4.登录: 链接redis
            redis_conn = get_redis_connection('carts')

            # 5.获取 hash 中的数据:  'user_id' : {sku_id: count}
            item_dict = redis_conn.hgetall('carts_%s' % request.user.id)

            # 6.获取 set 中的数据:  user_id : {sku_id1, sku_id2, ...}
            cart_selected = redis_conn.smembers('selected_%s' % request.user.id)

            cart_dict = {}

            # 7.拼接格式 ====> 拼接为 cookie中的格式
            for sku_id, count in item_dict.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in cart_selected
                }

        else:
            # 3.如果没有登录:
            # 3.1 读取cookie, 获取数据
            cookie_cart = request.COOKIES.get('carts')

            # 3.2 判断是否存在
            if cookie_cart:
                # 3.3 如果存在, 解密
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))

            else:
                # 3.4 如果不存在, 新建一个字典
                cart_dict = {}
        # 8. 获取字典中所有的keys
        sku_ids = cart_dict.keys()

        # 9. 根据所有的key值, 获取所有的商品
        skus = SKU.objects.filter(id__in=sku_ids)

        dict = []
        # 10. 遍历商品, 取出每一个, 拼接字典, 保存到list
        for sku in skus:
            dict.append({
                'id':sku.id,
                'name':sku.name,
                'default_image_url':sku.default_image_url,
                'count': cart_dict.get(sku.id).get('count'),
                'price':str(sku.price),
                'amount':str(sku.price * cart_dict.get(sku.id).get('count')),
                'selected':str(cart_dict.get(sku.id).get('selected'))
            })

        # 11. 拼接字典,
        context = {
            'cart_skus':dict
        }

        # 12. 返回
        return render(request, 'cart.html', context=context)

    def post(self, request):
        '''
        添加购物车数据
        :param request:
        :return:
        '''
        # 1.接收参数
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)

        # 2.校验参数
        if not all([sku_id, count]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            SKU.objects.get(id=sku_id)
        except Exception as e:
            return  http.HttpResponseForbidden('sku_id不存在')

        try:
            count = int(count)
        except Exception as e:
            return http.HttpResponseForbidden('count有误')

        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('selected有误')



        # 3.判断是否登录
        if request.user.is_authenticated:
            # 4.登录处理:
            # 6. 链接redis
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()

            # 7. 往hash set 添加数据
            # hash: user_id: {sku_id : count}
            pl.hincrby('carts_%s' % request.user.id,
                       sku_id,
                       count)

            if selected:
                # set:   'request.user.id': {sku_id1, sku_id2, ...}
                pl.sadd('selected_%s' % request.user.id,
                        sku_id)
            pl.execute()

            # 8. 返回
            return http.JsonResponse({'code':RETCODE.OK,
                                      'errmsg':'ok'})
        else:
            # 5.未登录处理
            # 9. 先从cookie中获取cookie值
            cookie_cart = request.COOKIES.get('carts')

            # 10. 判断该值是否存在
            if cookie_cart:
                # 11. 如果存在 ===>  解密
                # cart_dict = {
                #     'sku_id':{
                #         'count':12,
                #         'selected':True
                #     }
                # }
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                # 12. 如果不存在 ----> 新建一个字典
                cart_dict = {}

            # 13. 判断前端传入的sku_id是否在字典中
            if sku_id in cart_dict:
                # 14. 如果在, 个数累加
                count += cart_dict[sku_id]['count']

            # 15. 拼接格式  { sku_id : { 'count':个数, 'selected':True }}
            cart_dict[sku_id] = {
                'count':count,
                'selected':selected
            }
            # 16. 加密
            cart_data = base64.b64encode(pickle.dumps(cart_dict)).decode()

            response = http.JsonResponse({'code':RETCODE.OK,
                                          'errmsg':'ok'})

            # 17. 写入到cookie中
            response.set_cookie('carts', cart_data)

            # 18. 返回
            return response














