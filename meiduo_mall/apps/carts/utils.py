import base64
import pickle
from django_redis import get_redis_connection




def merge_cart_cookie_to_redis(request, response, user):
    '''
    把cookie的数据转到redis中, 删除cookie
    :return:
    '''
    # 1.从cookie中获取对应的数据
    cookie_cart = request.COOKIES.get('carts')

    # 2.判断数据是否存在
    if not cookie_cart:
        return response

    # 3.如果存在, 解密
    cart_dict = pickle.loads(base64.b64decode(cookie_cart))

    # # cookie:
    # sku_id : {
    #     'count':1,
    #     'selected':True
    # }
    #
    #
    # # hash:
    # uers_id : { sku_id : count}
    #
    # # set:
    # user_id : {sku_id1, sku_id2, ...}


    new_dict = {}

    new_add = []

    new_remove = []

    # 4.遍历, 整理数据为三部分:  {sku_id: count}  增加到set[sku_id1, ...]
    # 5.从set中删除: [sku_id2, ..]
    for sku_id, item in cart_dict.items():
        new_dict[sku_id] = item['count']

        if item['selected']:
            new_add.append(sku_id)
        else:
            new_remove.append(sku_id)


    # 6.链接redis
    redis_conn = get_redis_connection('carts')

    # 7.往hash中写入
    redis_conn.hmset('carts_%s' % user.id, new_dict)

    # 8.往set中写入
    if new_add:
        redis_conn.sadd('selected_%s' % user.id, *new_add)

    # 9.从set中删除
    if new_remove:
        redis_conn.srem('selected_%s' % user.id, *new_remove)

    # 10.删除cookie
    response.delete_cookie('carts')

    # 11. 返回
    return response
