from django.template import loader
import os
from contents.models import ContentCategory
from goods.utils import get_categories
from django.conf import settings

def generate_static_index_html():
    '''
    把首页生成静态页面
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
        'categories': categories,
        'contents': dict
    }
    # 6.返回
    # return render(request, 'index.html', context)
    # 获取首页模板文件
    template = loader.get_template('index.html')
    # 渲染首页html字符串
    html_text = template.render(context)
    # 将首页html字符串写入到指定目录，命名'index.html'
    file_path = os.path.join(settings.STATICFILES_DIRS[0], 'index.html')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
