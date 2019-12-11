from django import http
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render

# Create your views here.
from django.utils import timezone
from django.views import View

from goods.models import GoodsCategory, SKU
from goods.models import  GoodsVisitCount
from goods.utils import get_breadcrumb, get_categories, get_goods_and_spec
from meiduo_mall.utils.response_code import RETCODE
import datetime



class DetailVisitView(View):

    def post(self, request, category_id):
        '''
        保存访问记录到数据库
        :param request:
        :param category_id:
        :return:
        '''
        # 1.验证一下category_id
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return http.HttpResponseForbidden("缺少必传参数")


        # 2.生成一个当前的时间对象
        time = timezone.localtime()

        today_time_str = '%d-%02d-%02d' % (time.year, time.month, time.day)

        today_time = datetime.datetime.strptime(today_time_str, '%Y-%m-%d')

        # 3.根据当前时间, 区数据库中查询该表的对象是否存在
        try:
            obj = category.goodsvisitcount_set.get(date=today_time)
        except Exception as e:
            # 4.如果不存在, 新建一个
            obj = GoodsVisitCount()

        # 5.如果存在, 保存数据(category,  次数)
        try:
            obj.category = category
            obj.count += 1
            obj.save()
        except Exception as e:
            return http.HttpResponseForbidden('数据库保存失败')

        # 6.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok'})








class DetailView(View):

    def get(self, request, sku_id):
        '''
        接收商品id, 返回商品id对应的详情页
        :param request:
        :param sku_id:
        :return:
        '''
        categories = get_categories()


        # 获取商品所有规格选项:
        data = get_goods_and_spec(sku_id, request)

        breadcrumb = get_breadcrumb(data.get('goods').category3)



        # 拼接参数，生成静态 html 文件
        context = {
            'categories': categories,
            'goods': data.get('goods'),
            'specs': data.get('goods_specs'),
            'sku': data.get('sku'),
            'breadcrumb':breadcrumb
        }

        return render(request, 'detail.html', context=context)




class ListView(View):

    def get(self, request, category_id, page_num):
        '''
        接收参数, 返回商品列表页
        :param request:
        :param category_id: 商品类别id
        :param page_num: 用户想要的页码
        :return:
        '''
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except Exception as e:
            return http.HttpResponseForbidden('缺少必传参数')

        breadcrumb = get_breadcrumb(category)

        categories = get_categories()


        # 排序:
        sort = request.GET.get('sort')

        if sort == 'default':
            # 默认排序:
            sortkind = 'create_time'
        elif sort == 'price':
            # 价格:
            sortkind = 'price'
        else:
            # 人气(热度)
            sort = 'hot'
            sortkind = '-sales'

        # 获取的方法一:
        # category.sku_set.filter(category=category, is_launched=True)

        # 获取的方法二:
        skus = SKU.objects.filter(category=category, is_launched=True).order_by(sortkind)

        # 创建分页对象:
        paginator = Paginator(skus, 5)

        try:
            # 获取对应页面的数据(商品)
            page_skus = paginator.page(page_num)
        except EmptyPage:
            return http.HttpResponseForbidden('page_num对应的数据不存在')

        # 获取总页码:
        total_pages = paginator.num_pages

        context = {
            'categories': categories,
            'breadcrumb': breadcrumb,
            'total_page':total_pages,
            'page_skus':page_skus,
            'page_num':page_num,
            'sort':sort,
            'category':category
        }

        return render(request, 'list.html', context=context)


class HotGoodsView(View):

    def get(self, request, category_id):
        '''
        返回热销排行数据(2条)
        :param request:
        :param category_id:
        :return:
        '''
        # 1.根据category_id获取对应的类别商品(截串处理)
        skus = SKU.objects.filter(category_id=category_id,
                           is_launched=True).order_by('-sales')[:2]


        hot_skus = []
        # 2.遍历获取每一个, 整理格式
        for sku in skus:
            hot_skus.append({
                'id':sku.id,
                'default_image_url':sku.default_image_url,
                'name':sku.name,
                'price':sku.price
            })
        # 3.返回
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'hot_skus':hot_skus})


































