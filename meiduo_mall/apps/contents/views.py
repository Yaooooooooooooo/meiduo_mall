from django.shortcuts import render

# Create your views here.
from django.views import View

from contents.models import ContentCategory
from goods.utils import get_categories


class IndexView(View):

    def get(self, request):
        '''
        返回首页页面
        :param request:
        :return:
        '''
        # 商品分类数据:
        categories = get_categories()

        # 1.广告内容
        # 2.获取所有的广告类别
        content_categories = ContentCategory.objects.all()

        dict = {}
        # 3.遍历所有的广告类别, 获取每一个
        for cat in content_categories:

            # 4.定义一个字典, 把广告类别对应的内容放到字典中
            dict[cat.key] = cat.content_set.filter(status=True).order_by('sequence')

        # 5.拼接参数
        context = {
            'categories':categories,
            'contents':dict
        }
        # 6.返回
        return render(request, 'index.html', context)