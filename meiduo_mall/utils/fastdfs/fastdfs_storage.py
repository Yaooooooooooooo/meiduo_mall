from django.core.files.storage import Storage

from fdfs_client.client import Fdfs_client
from django.conf import settings


class FastDFSStorage(Storage):

    def save(self, name, content, max_length=None):
        '''
        上传图片到fastdfs
        :param name:
        :param content:
        :param max_length:
        :return:
        '''
        # 创建客户端对象:
        client = Fdfs_client(settings.FDFS_CLIENT_CONF)

        result = client.upload_by_buffer(content.read())

        # 判断是否上传成功:
        if result.get('Status') != 'Upload successed.':
            raise Exception('上传文件到FDFS系统失败')

        # 上传成功: 返回 file_id:
        file_id = result.get('Remote file_id')

        # 这个位置返回以后, django 自动会给我们保存到表字段里.
        return file_id

    # 我们再添加一个新的方法
    # 该方法会在我们上传之前,判断文件名称是否冲突
    def exists(self, name):
        # 根据上面的图片我们可知,
        # fdfs 中的文件名是由 fdfs 生成的, 所以不可能冲突
        # 我们返回 False: 永不冲突
        return False


    def url(self, name):

        return settings.FDFS_URL + name
