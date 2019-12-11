from django import http
from django.core.cache import cache
from django.shortcuts import render

# Create your views here.
from django.views import View

from areas.models import Area
from meiduo_mall.utils.response_code import RETCODE

class SubAreasView(View):

    def get(self, request, pk):
        '''
        接收参数(省份的id), 返回市区数据
        :param request:
        :return:
        '''
        # 1.根据pk, 获取省份和市区的数据(mysql)

        sub_data = cache.get('sub_areas_' + pk)

        if not sub_data:

            try:
                province_model = Area.objects.get(id=pk)

                sub_model_list = Area.objects.filter(parent=pk)

                sub_list = []

                # 2.遍历市区数据, 拼接格式
                for sub_model in sub_model_list:
                    sub_list.append({'id':sub_model.id,
                                     'name':sub_model.name})

                # 3.再次整理格式
                sub_data = {
                    'id':province_model.id,
                    'name':province_model.name,
                    'subs':sub_list
                }

                cache.set('sub_areas_' + pk, sub_data, 3600)

            except Exception as e:
                return http.JsonResponse({'code':RETCODE.DBERR,
                                          'errmsg':'获取市区数据错误'})


        # 4.返回(再次整理格式)
        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'sub_data':sub_data})






class ProvinceAreasView(View):

    def get(self, request):
        '''
        从mysql获取省份数据, 返回
        :param request:
        :return:
        '''
        province_list = cache.get('province_list')
        if not province_list:

            try:
                province_model_list = Area.objects.filter(parent__isnull=True)

                province_list = []

                for province_model in province_model_list:

                    province_list.append({'id':province_model.id,
                                          'name':province_model.name})
                cache.set('province_list', province_list, 3600)
            except Exception as e:

                return http.JsonResponse({'code':RETCODE.DBERR,
                                          'errmsg':'从数据库获取数据失败'})

        return http.JsonResponse({'code':RETCODE.OK,
                                  'errmsg':'ok',
                                  'province_list':province_list})

