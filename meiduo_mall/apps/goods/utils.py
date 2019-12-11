from collections import OrderedDict

from django.shortcuts import render

from goods.models import GoodsChannel, SKU


def get_goods_and_spec(sku_id, request):
    # 获取当前sku的信息
    try:
        sku = SKU.objects.get(id=sku_id)  # sku: iphonex 具体的商品
        sku.images = sku.skuimage_set.all()
    except SKU.DoesNotExist:
        return render(request, '404.html')

    # 面包屑导航信息中的频道
    goods = sku.goods  # IPHONEX: 类别

    # 构建当前商品的规格键
    # sku_key = [规格1参数id， 规格2参数id， 规格3参数id, ...]
    sku_specs = sku.skuspecification_set.order_by('spec_id')  # 灰: 1 + 256: a
    sku_key = []  # 一个具体的商品对应的选项:[1, a]
    for spec in sku_specs:
        sku_key.append(spec.option.id)

    # 获取当前商品的所有SKU
    skus = goods.sku_set.all()

    # 构建不同规格参数（选项）的sku字典
    # spec_sku_map = {
    #     (规格1参数id, 规格2参数id, 规格3参数id, ...): sku_id,
    #     (规格1参数id, 规格2参数id, 规格3参数id, ...): sku_id,
    #     ...
    # }

    # 灰: 1   金色: 2
    # 256: a  64: b
    spec_sku_map = {}
    for s in skus:
        # 获取sku的规格参数
        s_specs = s.skuspecification_set.order_by('spec_id')
        # 用于形成规格参数-sku字典的键
        key = []  # 一个商品:[2, b]  另一个商品:[1, a]  [1, b] [2, a]
        for spec in s_specs:
            key.append(spec.option.id)
        # 向规格参数-sku字典添加记录
        spec_sku_map[tuple(key)] = s.id

        # {(商品选项1, 商品选项1): sku_id}
        # {(2,b):123, (1,a):124, (1,b):231, (2,a):234}


    goods_specs = goods.goodsspecification_set.order_by('id') # [颜色, 内存]
    # goods_specs = goods.specs.order_by('id')
    # 若当前sku的规格信息不完整，则不再继续
    if len(sku_key) < len(goods_specs):
        return

    #  enumerate(goods_specs) ===> [0,颜色] [1, 内存]
    for index, spec in enumerate(goods_specs):
        # 复制当前sku的规格键
        # key = [规格1参数id， 规格2参数id， 规格3参数id, ...]
        key = sku_key[:]  # [1, a]
        # 该规格的选项
        spec_options = spec.specificationoption_set.all() # 金色 灰色

        for option in spec_options: # 金色# 2
            # 在规格参数sku字典中查找符合当前规格的sku
            key[index] = option.id  # key:[2, a]
            option.sku_id = spec_sku_map.get(tuple(key))

        spec.spec_options = spec_options


    data = {
        'goods':goods,
        'goods_specs':goods_specs,
        'sku':sku
    }

    return data



def get_categories():
    '''
    拼接商品分类数据, 返回
    :return:
    '''

    # 1.创建一个有序字典
    categories = OrderedDict()

    # 2.获取所有的channels
    channels = GoodsChannel.objects.order_by('group_id', 'sequence')

    # 3.遍历, 获取每一个channel
    for channel in channels:

        # 4.根据channel ===> group_id
        group_id = channel.group_id

        # 5.判断group_id是否在字典中
        if group_id not in categories:

            # 6.如果不在, 添加
            categories[group_id] = {"channels":[], "sub_cats":[]}

        # 7.channels对应的列表中添加数据
        cat1 = channel.category

        # 添加数据:
        categories[group_id]['channels'].append({
            'id':cat1.id,
            'name':cat1.name,
            'url':channel.url
        })

        # 8.获取单个的二级分类
        for cat2 in cat1.goodscategory_set.all():

            # 9.在二级分类上挂在一个属性sub_cats
            cat2.sub_cats = []

            # 10.获取单个的三级分类
            for cat3 in cat2.goodscategory_set.all():

                # 11.把三级添加到二级分类的sub_cats
                cat2.sub_cats.append(cat3)

                # 12.把二级分类放到sub_cats对应的列表中
            categories[group_id]['sub_cats'].append(cat2)

    # 13. 返回
    return categories


def get_breadcrumb(category):
    '''
    接收category, 判断cateogry是几级分类, 放入字典, 返回
    :param category:
    :return:
    '''
    # 1.定义一个字典
    breadcrumb = dict(
        cat1 = '',
        cat2 = '',
        cat3 = '',
    )
    # 2.判断category
    # 3.按照不同的分类, 放入字典中
    if category.parent is None:
        # 1
        breadcrumb['cat1'] = category
    elif category.goodscategory_set.count() == 0:
        # 3
        breadcrumb['cat3'] = category
        breadcrumb['cat2'] = category.parent
        breadcrumb['cat1'] = category.parent.parent
    else:
        # 2
        breadcrumb['cat2'] = category
        breadcrumb['cat1'] = category.parent


    # 4.返回字典
    return breadcrumb
