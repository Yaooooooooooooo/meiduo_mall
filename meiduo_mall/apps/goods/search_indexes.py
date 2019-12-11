from haystack import indexes

from goods.models import SKU


class SKUIndex(indexes.SearchIndex, indexes.Indexable):

    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        '''
        指定使用的表
        :return:
        '''
        return SKU

    def index_queryset(self, using=None):
        '''
        指定表中某一部分数据生成索引
        :param using:
        :return:
        '''
        return self.get_model().objects.filter(is_launched=True)